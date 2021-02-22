package collabai.group19;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.logging.Level;
import java.util.stream.Collectors;
import geniusweb.actions.Accept;
import geniusweb.actions.Action;
import geniusweb.actions.Offer;
import geniusweb.actions.PartyId;
import geniusweb.actions.Vote;
import geniusweb.actions.Votes;
//import geniusweb.bidspace.AllPartialBidsList;
import geniusweb.bidspace.BidsWithUtility;
import geniusweb.bidspace.Interval;
import geniusweb.inform.ActionDone;
import geniusweb.inform.Finished;
import geniusweb.inform.Inform;
import geniusweb.inform.OptIn;
import geniusweb.inform.Settings;
import geniusweb.inform.Voting;
import geniusweb.inform.YourTurn;
import geniusweb.issuevalue.Bid;
import geniusweb.issuevalue.DiscreteValue;
import geniusweb.opponentmodel.FrequencyOpponentModel;
import geniusweb.party.Capabilities;
import geniusweb.party.DefaultParty;
import geniusweb.profile.PartialOrdering;
import geniusweb.profile.Profile;
import geniusweb.profile.utilityspace.DiscreteValueSetUtilities;
import geniusweb.profile.utilityspace.LinearAdditive;
import geniusweb.profile.utilityspace.LinearAdditiveUtilitySpace;
import geniusweb.profile.utilityspace.UtilitySpace;
import geniusweb.profile.utilityspace.ValueSetUtilities;
import geniusweb.profileconnection.ProfileConnectionFactory;
import geniusweb.profileconnection.ProfileInterface;
import geniusweb.progress.Progress;
import geniusweb.progress.ProgressRounds;
import tudelft.utilities.immutablelist.ImmutableList;
import tudelft.utilities.logging.Reporter;

/**
 * A simple party that places random bids and accepts when it receives an offer
 * with sufficient utility.
 * <h2>parameters</h2>
 * <table >
 * <caption>parameters</caption>
 * <tr>
 * <td>minPower</td>
 * <td>This value is used as minPower for placed {@link Vote}s. Default value is
 * 2.</td>
 * </tr>
 * <tr>
 * <td>maxPower</td>
 * <td>This value is used as maxPower for placed {@link Vote}s. Default value is
 * infinity.</td>
 * </tr>
 * </table>
 */
public class Group19Party extends DefaultParty {

	private Bid lastReceivedBid = null;
	private PartyId me;
	//private final Random random = new Random();
	protected ProfileInterface profileint;
	private Progress progress;
	private Settings settings;
	private Votes lastvotes;
	private String protocol;
	
	// Keeping track of opponent model.
	private FrequencyOpponentModel fom = new FrequencyOpponentModel();
	
	// Keeping constants for threshold
	private double threshold;
	
	// Reused to benefit form caching as indicated by the constructor of this object
	private BidsWithUtility bwu;
	
	
	public Group19Party() {
	}

	public Group19Party(Reporter reporter) {
		super(reporter); // for debugging
	}

	@Override
	public void notifyChange(Inform info) {
		try {
			if (info instanceof Settings) {
				Settings settings = (Settings) info;
				this.profileint = ProfileConnectionFactory.create(settings.getProfile().getURI(), getReporter());
				this.me = settings.getID();
				this.progress = settings.getProgress();
				this.settings = settings;
				this.protocol = settings.getProtocol().getURI().getPath();
				LinearAdditiveUtilitySpace space = (LinearAdditiveUtilitySpace) profileint.getProfile();
				
				Map<String, ValueSetUtilities> valueutils = space.getUtilities();
				for (String issue : space.getDomain().getIssues()) {
					System.out.println(">>" + issue + " weigh t : " + space.getWeight(issue));
					ValueSetUtilities utils = valueutils.get(issue);
					// ignore the non−discrete in this demo
					if (!(utils instanceof DiscreteValueSetUtilities))
						continue;
					Map<DiscreteValue, BigDecimal> values = ((DiscreteValueSetUtilities) utils).getUtilities();
					for (DiscreteValue value : values.keySet()) {
						System.out.println(" utility( " + value + ")= " + values.get(value));
					}
				}
				
				// Initialize with domain and null reservation bid.
				this.fom = this.fom.with(space.getDomain(), null);
				
				// Initialize bwu field
				bwu = new BidsWithUtility (	(LinearAdditive) this.profileint.getProfile());
				
				// Define threshold
				Interval range = bwu.getRange();
				threshold = (range.getMax().doubleValue() + range.getMin().doubleValue())/2;
				
			} else if (info instanceof ActionDone) {
				Action otheract = ((ActionDone) info).getAction();
				this.fom = this.fom.with(otheract, progress);
				if (otheract instanceof Offer) {
					lastReceivedBid = ((Offer) otheract).getBid();
				}
//				System.out.println("received bid = " + lastReceivedBid + ", estimated opponent utility = " + this.fom.getUtility(lastReceivedBid));
			} else if (info instanceof YourTurn) {
				makeOffer();
			} else if (info instanceof Finished) {
				getReporter().log(Level.INFO, "Final ourcome:" + info);
			} else if (info instanceof Voting) {
				lastvotes = vote((Voting) info);
				getConnection().send(lastvotes);
			} else if (info instanceof OptIn) {
				// just repeat our last vote.
				getConnection().send(lastvotes);
			}
		} catch (Exception e) {
			throw new RuntimeException("Failed to handle info", e);
		}
		updateRound(info);
	}

	@Override
	public Capabilities getCapabilities() {
		return new Capabilities(new HashSet<>(Arrays.asList("SAOP")), Collections.singleton(Profile.class));
	}

	@Override
	public String getDescription() {
		return "places random bids until it can accept an offer with utility > threshold. "
				+ "Parameters minPower and maxPower can be used to control voting behaviour.";
	}

	/**
	 * Update {@link #progress}
	 * 
	 * @param info the received info. Used to determine if this is the last info of
	 *             the round
	 */
	private void updateRound(Inform info) {
		if (protocol == null)
			return;
		switch (protocol) {
		case "SAOP":
		case "SHAOP":
			if (!(info instanceof YourTurn))
				return;
			break;
		default:
			return;
		}
		// if we get here, round must be increased.
		if (progress instanceof ProgressRounds) {
			progress = ((ProgressRounds) progress).advance();
		}

	}

	/**
	 * send our next offer
	 */
	private void makeOffer() throws IOException {
		Action action;
		if ((protocol.equals("SAOP") || protocol.equals("SHAOP")) && isGood(lastReceivedBid)) {
			action = new Accept(me, lastReceivedBid);
		} else {
			// for demo. Obviously full bids have higher util in general
			//	Bid bid = null;
			//	for (int attempt = 0; attempt < 20 && !isGood(bid); attempt++) {
			//		long i = random.nextInt(bidspace.size().intValue());
			//		bid = bidspace.get(BigInteger.valueOf(i));
			//	}
			Bid newBid = getNewBid();
			if(newBid == null) newBid = this.lastReceivedBid;
			action = new Offer(me, newBid);
		}
		getConnection().send(action);
		updateThreshold();
	}

	/**
	 * @param bid the bid to check
	 * @return true iff bid is good for us.
	 */
	private boolean isGood(Bid bid) {
		if (bid == null)
			return false;
		Profile profile;
		try {
			profile = profileint.getProfile();
		} catch (IOException e) {
			throw new IllegalStateException(e);
		}
		if (profile instanceof UtilitySpace)
			return ((UtilitySpace) profile).getUtility(bid).doubleValue() > threshold;
		if (profile instanceof PartialOrdering) {
			return ((PartialOrdering) profile).isPreferredOrEqual(bid, profile.getReservationBid());
		}
		return false;
	}

	/**
	 * @param voting the {@link Voting} object containing the options
	 * 
	 * @return our next Votes.
	 */
	private Votes vote(Voting voting) throws IOException {
		Object val = settings.getParameters().get("minPower");
		Integer minpower = (val instanceof Integer) ? (Integer) val : 2;
		val = settings.getParameters().get("maxPower");
		Integer maxpower = (val instanceof Integer) ? (Integer) val : Integer.MAX_VALUE;

		Set<Vote> votes = voting.getBids().stream().distinct().filter(offer -> isGood(offer.getBid()))
				.map(offer -> new Vote(me, offer.getBid(), minpower, maxpower)).collect(Collectors.toSet());
		return new Votes(me, votes);
	}
	
	/**
	 * 
	 * @return Returns target utility.
	 * @throws IOException
	 */
	private double getTargetUtility() throws IOException {
		Double t = progress.get(System.currentTimeMillis());
		Interval range = bwu.getRange();
		double targetutil = (1-t) * (range.getMax().doubleValue() - threshold) + threshold;
		return targetutil;
	}
	
	/**
	 * 
	 * @return A new Bid
	 * @throws IOException
	 */
	private Bid getNewBid() throws IOException {
		BigDecimal target = new BigDecimal(getTargetUtility());
		// Changed this line to not use the "0.01" but range.getMax() to avoid an empty bid list
		// ImmutableList<Bid> bids = bwu.getBids(new Interval(target, target.add(new BigDecimal("0.01"))));
		ImmutableList<Bid> bids = bwu.getBids(new Interval(target, bwu.getRange().getMax()));
		if (bids.size().compareTo(BigInteger.ZERO) == 0) return null;
		
		// Loop through bids to get the Highest Utility bid from OpponentModel
        Bid highestBid = bids.get(0);
        for(Bid bid : bids) {
            if(fom.getUtility(bid).compareTo(fom.getUtility(highestBid)) > 1) {
            	highestBid = bid;
            }
        }
		return bids.get(BigInteger.ZERO);
	}
	
	/**
	 * 
	 * @return Nash product
	 */
	private void updateThreshold() throws IOException {
		BigDecimal ownUtil = bwu.getRange().getMax();
		BigDecimal opponentUtil = this.fom.getUtility(lastReceivedBid);
		double nashUtil = ownUtil.doubleValue() * opponentUtil.doubleValue();
		this.threshold = nashUtil; 
	}
	
	
	/**
	 * 
	 * @return The Bid containing the maximum utility.
	 * @throws IOException
	 */
	//	private Bid getMaxUtilityBid() throws IOException {
	//		BidsWithUtility bwu = new BidsWithUtility (	(LinearAdditive) this.profileint.getProfile() );
	//		BigDecimal maxutil = bwu.getRange().getMax();
	//		ImmutableList<Bid> bids = bwu.getBids(new Interval(maxutil.subtract (new BigDecimal("0.01")), maxutil));
	//		if(bids.size().compareTo(BigInteger.ZERO) == 0) return null;
	//		return bids.get(BigInteger.ZERO);
	//	}

}
