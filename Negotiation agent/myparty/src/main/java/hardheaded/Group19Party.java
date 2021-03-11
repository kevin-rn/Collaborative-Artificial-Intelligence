package hardheaded;


import java.awt.geom.Point2D;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.DecimalFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Random;
import java.util.Set;
import java.util.logging.Level;
import java.util.stream.Collectors;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.json.simple.JSONObject;
import org.json.simple.JSONArray;
import org.json.simple.parser.JSONParser;

import geniusweb.actions.Accept;
import geniusweb.actions.Action;
import geniusweb.actions.Offer;
import geniusweb.actions.PartyId;
import geniusweb.actions.Vote;
import geniusweb.actions.Votes;
import geniusweb.bidspace.AllBidsList;
import geniusweb.bidspace.AllPartialBidsList;
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
	private Bid secondLastReceivedBid = null;
	private BigDecimal lastMadeBidUtility;
	private PartyId me;
	private final Random random = new Random();
	protected ProfileInterface profileint;
	private Progress progress;
	private Settings settings;
	private Votes lastvotes;
	private String protocol;
	private double targetUtility;
	private Bid maxBid;
	private FrequencyOpponentModel fop;
	private ArrayList<Bid> opponentBids;
	private ArrayList<Bid> myBids;
	private ArrayList<Offer> offers;
	
	private double Ka = 0.05;
    private double e = 0.05;
    private double discountF = 1D;
    private double lowestYetUtility = 1D;
	private double maxUtil = 1D;
	private double minUtil = 0D;
	
	private String otherDomain = "jobs2";
	

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
				System.out.println(settings.getProfile());
				this.profileint = ProfileConnectionFactory
						.create(settings.getProfile().getURI(), getReporter());
				this.me = settings.getID();
				this.progress = settings.getProgress();
				this.settings = settings;
				this.protocol = settings.getProtocol().getURI().getPath();
				this.targetUtility = maxUtil;
//				updateTargetUtility();
				this.fop = new FrequencyOpponentModel();
				fop = fop.with(profileint.getProfile().getDomain(), profileint.getProfile().getReservationBid());
				opponentBids = new ArrayList<>();
				myBids = new ArrayList<>();
				offers = new ArrayList<>();
//				BSelector = new BidSelector((UtilitySpace) this.profileint.getProfile());
//				Entry<BigDecimal, Bid> highestBid = BSelector.BidList.lastEntry();

//				maxUtil = ((UtilitySpace) this.profileint.getProfile()).getUtility(highestBid.getValue()).doubleValue();
				maxUtil = ((UtilitySpace) this.profileint.getProfile()).getUtility(getMaxUtilityBid()).doubleValue();
				Bid reservationBid = this.profileint.getProfile().getReservationBid();
				if(reservationBid != null) minUtil = ((UtilitySpace) this.profileint.getProfile()).getUtility(reservationBid).doubleValue();

			} else if (info instanceof ActionDone) {
				Action otheract = ((ActionDone) info).getAction();
				fop = fop.with(otheract, progress);
//				System.out.println(fop.toString());
				if (otheract instanceof Offer) {
					Offer otherOffer = (Offer) otheract;
					if(!otherOffer.getActor().equals(this.me)) {
						offers.add(otherOffer);
//						System.out.println(otherOffer.getBid());
						secondLastReceivedBid = lastReceivedBid;
						lastReceivedBid = otherOffer.getBid();
	//					if(profileint.getProfile().getDomain().isComplete(lastReceivedBid)==null) {
	//						System.out.print(lastReceivedBid + ": ");
	//						System.out.println(fop.getUtility(lastReceivedBid));
							opponentBids.add(lastReceivedBid);
	//						updateTargetUtility();
	//					}
					}
				}
			} else if (info instanceof YourTurn) {
				this.targetUtility = get_p();
//				this.targetUtility = getTargetUtility();
				makeOffer();
			} else if (info instanceof Finished) {
				Finished fin = (Finished) info;
				System.out.println(this.getClass());
				Set<PartyId> keys = fin.getAgreement().getMap().keySet();
				Profile profile = this.profileint.getProfile();
//				getAllBidOptions();
				getUtilityOther(offers, otherDomain, !fin.getAgreement().getMap().isEmpty());
				paretoOptimalFront(getAllBidOptionsUtilities(otherDomain));
				String print = "";
				int i=0; 
				for(PartyId key: keys) {
					if(i==0) {
						print += key + ": " + ((UtilitySpace) profile).getUtility(fin.getAgreement().getMap().get(key)) + "\n";
						i++;
					}
//					if(i==1) print += key + ": " + fop.getUtility(fin.getAgreement().getMap().get(key)) + "\n";
//					i++;
					else continue;
				}
				getReporter().log(Level.INFO, "Final outcome:" + info + "Utilities: \n" + print);
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
		return new Capabilities(
				new HashSet<>(Arrays.asList("SAOP")),
				Collections.singleton(Profile.class));
	}

	@Override
	public String getDescription() {
		return "places random bids until it can accept an offer with utility > target utility. "
				+ "Parameters minPower and maxPower can be used to control voting behaviour.";
	}

	/**
	 * Update {@link #progress}
	 * 
	 * @param info the received info. Used to determine if this is the last info
	 *             of the round
	 */
	private void updateRound(Inform info) {
		if (protocol == null)
			return;
		switch (protocol) {
		case "SAOP":
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
	
//	/**
//	 * send our next offer WITHOUT ACCEPTANCE STRATEGY
//	 */
//	private void makeOffer() throws IOException {
//		Action action;
//		
//		if ((protocol.equals("SAOP"))
//				&& isGood(lastReceivedBid)) {
//			action = new Accept(me, lastReceivedBid);
//		} else {			
//			Bid offerBid = makeBid();
//			action = new Offer(me, offerBid);
//			offers.add((Offer) action);
//		}
//		getConnection().send(action);
//	}

	/**
	 * send our next offer WITH ACCEPTANCE STRATEGY
	 */
	private void makeOffer() throws IOException {
		Action action;
		Bid offerBid = makeBid();
		
		if ((protocol.equals("SAOP"))
				&& isAcceptCombi(offerBid)) {
			action = new Accept(me, lastReceivedBid);
		} else {			
			action = new Offer(me, offerBid);
			offers.add((Offer) action);
		}
		
		getConnection().send(action);
	}
	
	
	private Bid makeBid() throws IOException {
		Bid bid = getParetoOptimalBid();

		if(bid==null) {
			//System.out.println("NULL");
			AllPartialBidsList bidspace = new AllPartialBidsList(
					profileint.getProfile().getDomain());
		
			for (int attempt = 0; attempt < 20 && !isGood(bid); attempt++) {
				long i = random.nextInt(bidspace.size().intValue());
				bid = bidspace.get(BigInteger.valueOf(i));
			}
		}
		
		return bid;
	}
	
	private boolean isAcceptNext(Profile profile, Bid ourUpcomingBid) {
		if (this.lastReceivedBid == null) {			
			return false;
		}
		
//		System.out.println("isAcceptNext: " 
//		+ "((PartialOrdering) profile).isPreferredOrEqual( " + (((UtilitySpace) profile).getUtility(this.lastReceivedBid).doubleValue()) 
//		+ " , " + (((UtilitySpace) profile).getUtility(ourUpcomingBid).doubleValue()) + ") = " +
//		((PartialOrdering) profile).isPreferredOrEqual(this.lastReceivedBid, ourUpcomingBid));
		
		return ((PartialOrdering) profile).isPreferredOrEqual(this.lastReceivedBid, ourUpcomingBid);
	}
	
	private boolean isAcceptTime(long T) {
//		System.out.println("isAcceptTime: " 
//				+ "progress.get(T) = " + progress.get(T) + " "
//				+ T + " >= " + progress.getTerminationTime().getTime() + " - 5 = " + 
//				(T >= progress.getTerminationTime().getTime() - 5L));
		
		if (progress.get(T) == 1L || T >= progress.getTerminationTime().getTime() - 5L) {
			return true;
		} else {
			return false;
		}
	}
	
	private boolean isAcceptConst(Profile profile) {
		if (this.lastReceivedBid == null) {			
			return false;
		}
		
//		System.out.println("isAcceptConst: " 
//				+ (((UtilitySpace) profile).getUtility(this.lastReceivedBid).doubleValue()) + " > " + targetUtility + " = " +
//				(((UtilitySpace) profile).getUtility(this.lastReceivedBid).doubleValue() > targetUtility));
	
		return ((UtilitySpace) profile).getUtility(this.lastReceivedBid).doubleValue() > targetUtility;
	}
	
	/**
	 * Uses combined acceptance strategies to decide whether to accept the last received bid of opponent.
	 * @param ourUpcomingBid that offer that we want to offer next.
	 * @return True if we accept the last received bid, otherwise False.
	 * @throws IOException IOException when something goes wrong.
	 */
	private boolean isAcceptCombi(Bid ourUpcomingBid) throws IOException {
		Profile profile;
		try {
			profile = profileint.getProfile();
		} catch (IOException e) {
			throw new IllegalStateException(e);
		}
		System.out.println("isAcceptCombi: " 
				+ (isAcceptNext(profile, ourUpcomingBid) || (isAcceptTime(System.currentTimeMillis()) && isAcceptConst(profile))));
		
		return isAcceptNext(profile, ourUpcomingBid) || (isAcceptTime(System.currentTimeMillis()) && isAcceptConst(profile));
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
			return ((UtilitySpace) profile).getUtility(bid).doubleValue() > targetUtility;
		if (profile instanceof PartialOrdering) {
			return ((PartialOrdering) profile).isPreferredOrEqual(bid,
					profile.getReservationBid());
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
		Integer maxpower = (val instanceof Integer) ? (Integer) val
				: Integer.MAX_VALUE;

		Set<Vote> votes = voting.getBids().stream().distinct()
				.filter(offer -> isGood(offer.getBid()))
				.map(offer -> new Vote(me, offer.getBid(), minpower, maxpower))
				.collect(Collectors.toSet());
		return new Votes(me, votes);
	}
	
	private Bid getMaxUtilityBid() throws IOException {
		BidsWithUtility bwu = new BidsWithUtility(
				(LinearAdditive) this.profileint.getProfile());
		BigDecimal maxutil = bwu.getRange().getMax();
		ImmutableList<Bid> bids = bwu.getBids(new Interval(
				maxutil.subtract(new BigDecimal("0.01")), maxutil));
		
		if(bids.size().compareTo(BigInteger.ZERO)== 0)
			return null;
		return bids.get(BigInteger.ZERO);
	}
//	
	private Bid getParetoOptimalBid() throws IOException {
		BidsWithUtility bwu = new BidsWithUtility(
				(LinearAdditive) this.profileint.getProfile());
//		BigDecimal maxutil = bwu.getRange().getMax();
//		System.out.println(targetUtility);
		BigDecimal targetutil = new BigDecimal(targetUtility);
		double interval = 0.01;
		ImmutableList<Bid> bids = null;
		do {
		bids = bwu.getBids(new Interval(targetutil.subtract(new BigDecimal(interval)), targetutil.add(new BigDecimal(interval))));
		interval += 0.01;
		}while(bids.size().compareTo(BigInteger.ZERO)== 0);
//		if(bids.size().compareTo(BigInteger.ZERO)== 0)
//			return null;
		Bid maxBid = bids.get(0);
		for(Bid bid: bids) {
//			System.out.println(fop.getUtility(bid) + " > " + fop.getUtility(maxBid));
			if(fop.getUtility(bid).compareTo(fop.getUtility(maxBid))==1)
				maxBid = bid;
		}
		return maxBid;
	}
	
	private Bid newBidAbsoluteTFT() throws IOException{
		
		BidsWithUtility bwu = new BidsWithUtility(
				(LinearAdditive) this.profileint.getProfile());
		
		if(lastReceivedBid == null || secondLastReceivedBid == null) {
			this.lastMadeBidUtility = new BigDecimal(this.targetUtility);
			return bwu.getExtremeBid(true);
		}
		
		Profile profile = this.profileint.getProfile();

		BigDecimal last = ((UtilitySpace) profile).getUtility(this.lastReceivedBid);
		BigDecimal secondLast = ((UtilitySpace) profile).getUtility(this.secondLastReceivedBid);
		BigDecimal diff = secondLast.subtract(last); //How much the newly done bid is better for yourself
		BigDecimal newUtility = this.lastMadeBidUtility.subtract(diff).max(BigDecimal.ZERO); //New utility changes with -diff.		

//		ImmutableList<Bid> bids = bwu.getBids(new Interval(newUtility.subtract(new BigDecimal("0.05")), newUtility));
//		
//		if(bids.size().compareTo(BigInteger.ZERO)== 0)
//			return null;
		
		double interval = 0.01;
		ImmutableList<Bid> bids = null;
		do {
			bids = bwu.getBids(new Interval(newUtility.subtract(new BigDecimal(interval)), newUtility.add(new BigDecimal(interval))));
			interval += 0.01;
		}while(bids.size().compareTo(BigInteger.ZERO)== 0);
		
		Bid bid = bids.get(0);
		
		this.lastMadeBidUtility = ((UtilitySpace) profile).getUtility(bid);

		return bid;
		
		
	}
	
	private Bid newBidRelativeTFT() throws IOException{
		if(lastReceivedBid == null || secondLastReceivedBid == null) {
			this.lastMadeBidUtility = new BigDecimal(this.targetUtility);
			return null;
		}
		
		Profile profile = this.profileint.getProfile();

		BigDecimal last = ((UtilitySpace) profile).getUtility(this.lastReceivedBid);
		BigDecimal secondLast = ((UtilitySpace) profile).getUtility(this.secondLastReceivedBid);
//		BigDecimal diff = secondLast.subtract(last); //How much the newly done bid is better for yourself
		BigDecimal change = last.divide(secondLast, RoundingMode.HALF_UP);
		BigDecimal newUtility = this.lastMadeBidUtility.multiply(change).min(BigDecimal.ONE); //New utility changes with -diff.		
		BidsWithUtility bwu = new BidsWithUtility(
				(LinearAdditive) this.profileint.getProfile());
		ImmutableList<Bid> bids = bwu.getBids(new Interval(newUtility.subtract(new BigDecimal("0.05")), newUtility));
		
		if(bids.size().compareTo(BigInteger.ZERO)== 0)
			return null;
		
		Bid bid = bids.get(0);
		
		this.lastMadeBidUtility = ((UtilitySpace) profile).getUtility(bid);

		return bid;
		
		
	}
	
	private Bid newBidAverageTFT() throws IOException{
		int lastN = 5;
		int bidsListSize = opponentBids.size();

		if(bidsListSize<5) {
			this.targetUtility = getTargetUtility();
			this.lastMadeBidUtility = new BigDecimal(this.targetUtility);
			return null;
		}
		
		Profile profile = this.profileint.getProfile();
		
		BigDecimal sum = BigDecimal.ZERO;
		List<Bid> lastNBids = opponentBids.subList(bidsListSize-lastN, bidsListSize);
		for(int i=0; i<lastN-1; i++) {
			Bid fstBid = lastNBids.get(i);
			Bid sndBid = lastNBids.get(i+1);
			BigDecimal fst = ((UtilitySpace) profile).getUtility(fstBid);
			BigDecimal snd = ((UtilitySpace) profile).getUtility(sndBid);
			BigDecimal diff = snd.subtract(fst); 
			sum.add(diff);
		}
		BigDecimal avg = sum.subtract(new BigDecimal(lastN-1));

		
		BigDecimal newUtility = this.lastMadeBidUtility.subtract(avg); //New utility changes with -avg.		
		BidsWithUtility bwu = new BidsWithUtility(
				(LinearAdditive) this.profileint.getProfile());
		ImmutableList<Bid> bids = bwu.getBids(new Interval(newUtility.subtract(new BigDecimal("0.05")), newUtility));
		
		if(bids.size().compareTo(BigInteger.ZERO)== 0)
			return null;
		
		Bid bid = bids.get(0);
		
		this.lastMadeBidUtility = ((UtilitySpace) profile).getUtility(bid);
		this.targetUtility = this.lastMadeBidUtility.doubleValue();

		return bid;
		
		
	}
	
	private double getUtilityOther(ArrayList<Offer> offers, String otherDomain, boolean agreement) {
		try {
		Profile profile = this.profileint.getProfile();	
			
		JSONParser parser = new JSONParser();

		Object obj = parser.parse(new FileReader("src/test/resources/" + this.profileint.getProfile().getDomain().getName() + "/" + otherDomain + ".json"));
		JSONObject jsonObject = (JSONObject) obj;
//		bid.getIssueValues();
		JSONObject laus = (JSONObject) jsonObject.get("LinearAdditiveUtilitySpace");
		JSONObject issueWeights = (JSONObject) laus.get("issueWeights");
		JSONObject issueUtilities = (JSONObject) laus.get("issueUtilities");
				
		ArrayList<Double> otherUtilities = new ArrayList<>();
		ArrayList<Double> myUtilities = new ArrayList<>();
//		ArrayList<Point2D.Double> points = new ArrayList<>();
		ArrayList<PartyId> partyIds = new ArrayList<>();
		for(Offer offer: offers) {
			double sum = 0;
			Bid bid = offer.getBid();
			for(String issue: bid.getIssues()) {
//				System.out.println("issue weight: " + issueWeights.get(issue));
				JSONObject values = (JSONObject) ((JSONObject) (((JSONObject) issueUtilities.get(issue)).get("discreteutils"))).get("valueUtilities");
//				System.out.println("issue utility: " + values.get(bid.getValue(issue).toString().replace("\"", "")));
				String issueUtility = values.get(bid.getValue(issue).toString().replace("\"", "")).toString();
	//			System.out.println(StringUtils.difference("1 TB", (bid.getValue(issue).toString())));
				sum += Double.parseDouble(issueWeights.get(issue).toString()) * Double.parseDouble(issueUtility);
			}
//			System.out.println(sum);
			otherUtilities.add(sum);
			myUtilities.add(((UtilitySpace) profile).getUtility(bid).doubleValue());
//			Point2D.Double
			partyIds.add(offer.getActor());
//			Profile profile = this.profileint.getProfile();
//			System.out.println(((UtilitySpace) profile).getUtility(bid));
		}
//		System.out.println(myUtilities);
//		System.out.println(otherUtilities);
//		System.out.println(partyIds);
		
		String writeStr1 = "";
		String writeStr2 = "";
		for(int i=0; i<partyIds.size(); i++) {
			writeStr1 += (otherUtilities.get(i) + ", " + myUtilities.get(i) + "\n");
			String[] partyIdSplit = partyIds.get(i).toString().split("_");
			int splLength = partyIdSplit.length;
			writeStr2 += (partyIdSplit[splLength-2] + "_" +  partyIdSplit[splLength-1] + "\n");

		}
		if(!agreement) writeStr1 += "0.0, 0.0\n";
		File f = new File("src/test/resources/utilities.txt");
		f.createNewFile();
		FileWriter fw = new FileWriter(f);
		fw.write(writeStr1);
		fw.close();
		
		File f2 = new File("src/test/resources/utilitiesPartyIds.txt");
		f2.createNewFile();
		FileWriter fw2 = new FileWriter(f2);
		fw2.write(writeStr2);
		fw2.close();
		
//		
		return 0;
		} catch (Exception e) {
			e.printStackTrace();
		}
		return 0;
	}
	
	private ArrayList<Point2D.Double> getUtilityBids(List<Bid> bids, String otherDomain) {
		try {
		Profile profile = this.profileint.getProfile();	
			
		JSONParser parser = new JSONParser();

		Object obj = parser.parse(new FileReader("src/test/resources/" + this.profileint.getProfile().getDomain().getName() + "/" + otherDomain + ".json"));
		JSONObject jsonObject = (JSONObject) obj;
//		bid.getIssueValues();
		JSONObject laus = (JSONObject) jsonObject.get("LinearAdditiveUtilitySpace");
		JSONObject issueWeights = (JSONObject) laus.get("issueWeights");
		JSONObject issueUtilities = (JSONObject) laus.get("issueUtilities");
				
//		ArrayList<Double> otherUtilities = new ArrayList<>();
//		ArrayList<Double> myUtilities = new ArrayList<>();
		ArrayList<Point2D.Double> points = new ArrayList<>();
		for(Bid bid: bids) {
			double sum = 0;
			for(String issue: bid.getIssues()) {
//				System.out.println("issue weight: " + issueWeights.get(issue));
				JSONObject values = (JSONObject) ((JSONObject) (((JSONObject) issueUtilities.get(issue)).get("discreteutils"))).get("valueUtilities");
//				System.out.println("issue utility: " + values.get(bid.getValue(issue).toString().replace("\"", "")));
				String issueUtility = values.get(bid.getValue(issue).toString().replace("\"", "")).toString();
	//			System.out.println(StringUtils.difference("1 TB", (bid.getValue(issue).toString())));
				sum += Double.parseDouble(issueWeights.get(issue).toString()) * Double.parseDouble(issueUtility);
			}
//			System.out.println(sum);
//			otherUtilities.add(sum);
//			myUtilities.add(((UtilitySpace) profile).getUtility(bid).doubleValue());
			Point2D.Double point = new Point2D.Double(sum, ((UtilitySpace) profile).getUtility(bid).doubleValue());
			points.add(point);
//			Profile profile = this.profileint.getProfile();
//			System.out.println(((UtilitySpace) profile).getUtility(bid));
		}
//		System.out.println(myUtilities);
//		System.out.println(otherUtilities);
//		System.out.println(partyIds);
		
		return points;
		
		} catch (Exception e) {
			e.printStackTrace();
		}
		return null;
	}
	
	private void getAllBidOptions() {
		try{
//		
//		O
		Profile profile = this.profileint.getProfile();
		AllBidsList bidspace = new AllBidsList(
				profileint.getProfile().getDomain());
//		System.out.println(bidspace);

		File f = new File("src/test/resources/log.txt");
		f.createNewFile();
		FileWriter fw = new FileWriter(f);
//		fw.write(jsonString);
//		fw.close();
		List<Bid> newBidspace = new ArrayList<Bid>();
		for(Bid bid: bidspace) {
			newBidspace.add(bid);
		}
//		ObjectMapper mapper = new ObjectMapper();
//	    String jsonString = JSONArray.toJSONString(newBidspace);
//	    JSONArray jsonarray = new JSONArray();
//	    jsonarray.addAll(newBidspace);
////	    System.out.println(jsonString);
//
//		JSONObject obj = new JSONObject();
//		obj.put("bids", jsonarray);
//		fw.write(obj.toString());
//		fw.close();
		
		} catch (Exception e) {
			e.printStackTrace();
		}
	}
	
	private ArrayList<Point2D.Double> getAllBidOptionsUtilities(String domain){
		try {
		Profile profile = this.profileint.getProfile();
		AllBidsList bidspace = new AllBidsList(
				profileint.getProfile().getDomain());
		List<Bid> newBidspace = new ArrayList<Bid>();
		for(Bid bid: bidspace) {
			newBidspace.add(bid);
		}
		return getUtilityBids(newBidspace, domain);
		
		}catch (Exception e) {
			e.printStackTrace();
		}
		return null;
	}
	
	private ArrayList<Point2D.Double> paretoOptimalFront(ArrayList<Point2D.Double> allPoints){
		ArrayList<Point2D.Double> pom = new ArrayList<>();
		pom.addAll(allPoints);
		for(Point2D.Double point: allPoints) {
			for(Point2D.Double point2: allPoints) {
				if(point.equals(point2)) continue;
//				point2.x >= point.x || point2.y > point.y;
				if((point2.x >= point.x && point2.y > point.y) || (point2.x > point.x && point2.y >= point.y)) {
					pom.remove(point);
				}
			}
		}
		Collections.sort(pom, Comparator.comparingDouble(Point2D.Double::getX));
		try {
		File f = new File("src/test/resources/pom.txt");
		f.createNewFile();
		FileWriter fw = new FileWriter(f);
		fw.write(pom.toString().replaceAll("Point2D.Double", "").replaceAll("\\[", "").replaceAll("\\]\\, ", "\n").replaceAll("\\]", ""));
		fw.close();
		} catch (Exception e) {
			e.printStackTrace();
		}
		return pom;
	}

	
//	private Bid getNewBid() throws IOException {
//		BidsWithUtility bwu = new BidsWithUtility(
//				(LinearAdditive) this.profileint.getProfile());
//		BigDecimal targetutil = new BigDecimal(targetUtility);
//		Interval range = bwu.getRange();
//		ImmutableList<Bid> bids = bwu.getBids(new Interval(
//				targetutil, range.getMax()));
//		
////		ImmutableList<Bid> bids = bwu.getBids(new Interval(
////				targetutil.subtract(new BigDecimal("0.01")), targetutil));
//		
//		if(bids.size().compareTo(BigInteger.ZERO)== 0)
//			return null;
//		Random rd = new Random();
////		System.out.println(bids.size().intValue());
//		int randomInt = rd.nextInt(bids.size().intValue());
//		System.out.println(randomInt);
//		System.out.println(bids.get(randomInt));
//		return bids.get(randomInt);
////		return bids.get(0);
//	}
//	
	private double getTargetUtility() throws IOException {
		BidsWithUtility bwu = new BidsWithUtility(
				(LinearAdditive) this.profileint.getProfile());
		Double t = progress.get(System.currentTimeMillis());
		Interval range = bwu.getRange();
		double avg = (range.getMax().doubleValue()+range.getMin().doubleValue())/2;
		double targetutil = (1-t) * (range.getMax().doubleValue() - avg) + avg;
//		System.out.println(targetutil);
		return targetutil;
	}
	
	 /**
     * This function calculates the concession amount based on remaining time,
     * initial parameters, and, the discount factor.
     * 
     * @return double: concession step
     */
    public double get_p() {

            double time = progress.get(System.currentTimeMillis());
            double Fa;
            double p = 1D;
            double step_point = discountF;
            double tempMax = maxUtil;
            double tempMin = minUtil;
            double tempE = e;
            double ignoreDiscountThreshold = 0.9D;

            if (step_point >= ignoreDiscountThreshold) {
                    Fa = Ka + (1 - Ka) * Math.pow(time / step_point, 1D / e);
                    p = minUtil + (1 - Fa) * (maxUtil - minUtil);
            } else if (time <= step_point) {
                    tempE = e / step_point;
                    Fa = Ka + (1 - Ka) * Math.pow(time / step_point, 1D / tempE);
                    tempMin += Math.abs(tempMax - tempMin) * step_point;
                    p = tempMin + (1 - Fa) * (tempMax - tempMin);
            } else {
                    // Ka = (maxUtil - (tempMax -
                    // tempMin*step_point))/(maxUtil-minUtil);
                    tempE = 30D;
                    Fa = (Ka + (1 - Ka) * Math
                                    .pow((time - step_point) / (1 - step_point), 1D / tempE));
                    tempMax = tempMin + Math.abs(tempMax - tempMin) * step_point;
                    p = tempMin + (1 - Fa) * (tempMax - tempMin);
            }
            System.out.println("P: " + p);
            System.out.println("P: " + (minUtil + (1 - (0.05 + 0.95 * Math.pow(time, 20))) * (maxUtil - minUtil)));
            System.out.println("Time: " + time);
            System.out.println("MinUtil: " + minUtil);
            return p;
    }
	
//	private void updateTargetUtility() throws IOException {
//		if(progress.get(System.currentTimeMillis()) <0.3) {
//			this.targetUtility = getTargetUtility();
//		} else {
//			if(lastReceivedBid == null) {
//				this.targetUtility = getTargetUtility();
//			} else {
//				Profile profile = this.profileint.getProfile();
//				
//				if(maxBid == null) {
//					this.targetUtility = ((UtilitySpace) profile).getUtility(lastReceivedBid).doubleValue();
//	//				this.nashmax = newutilproduct.doubleValue();
//					this.maxBid = lastReceivedBid;
//				} else {
//					BigDecimal max = BigDecimal.ZERO;
//					for(Bid opponentBid: opponentBids) {
//						BigDecimal myutil = ((UtilitySpace) profile).getUtility(opponentBid);
//						BigDecimal otherutil = fop.getUtility(opponentBid);
//						
//						BigDecimal newutilproduct = (otherutil.multiply(myutil));
////						System.out.println("my: " + myutil.doubleValue() + ", other: " + otherutil.doubleValue() + ", product: " + newutilproduct);
//						
////						double curnashmax = fop.getUtility(maxBid).doubleValue()*targetUtility;
//						
////						System.out.println(max + " < " + newutilproduct.doubleValue());
//		
//						if(max.compareTo(newutilproduct) == -1) {
//							max = newutilproduct;
//							this.targetUtility = myutil.doubleValue();
//			//				this.nashmax = newutilproduct.doubleValue();
//							this.maxBid = opponentBid;
//		
//						}
//					}
//
//					System.out.println("nashmax: " + fop.getUtility(maxBid).doubleValue()*targetUtility + " with targetutil: " + this.targetUtility);
//				}
//		}
//			
//			
//		}
//	}
//	
	private double getMaxUtility() throws IOException {
		BidsWithUtility bwu = new BidsWithUtility(
				(LinearAdditive) this.profileint.getProfile());
		BigDecimal maxutil = bwu.getRange().getMax();

		return maxutil.doubleValue();
	}
	

}
