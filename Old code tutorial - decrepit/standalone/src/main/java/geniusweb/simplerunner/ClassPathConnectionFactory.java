package geniusweb.simplerunner;

import java.io.IOException;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.LinkedList;
import java.util.List;

import geniusweb.actions.Action;
import geniusweb.actions.PartyId;
import geniusweb.inform.Inform;
import geniusweb.party.Party;
import geniusweb.protocol.partyconnection.ProtocolToPartyConn;
import geniusweb.protocol.partyconnection.ProtocolToPartyConnFactory;
import geniusweb.references.Reference;
import tudelft.utilities.repository.NoResourcesNowException;

/**
 * A connectionfactory that only accepts URLs of the form
 * <code>classpath:org/my/package/class</code>
 * 
 */
public class ClassPathConnectionFactory implements ProtocolToPartyConnFactory {
	private static final String SCHEME = "classpath";
	private static int serialcounter = 1;
	private final static URI PROTOCOLURI = uri("protocol:protocol");

	@Override
	public ProtocolToPartyConn connect(Reference reference) {
		// set up the whole other party including the connection to it.
		String classpath = getClassPath(reference.getURI());
		Party party = instantiate(classpath);

		BasicConnection<Inform, Action> party2protocol = new BasicConnection<Inform, Action>(
				reference, PROTOCOLURI);
		BasicConnectionWithParty protocol2party = new BasicConnectionWithParty(
				reference,
				uri("classpath:" + reference.getURI().getSchemeSpecificPart()
						+ "." + (serialcounter++)));
		party2protocol.init(action -> protocol2party.notifyListeners(action));
		protocol2party.init(info -> party2protocol.notifyListeners(info));

		party.connect(party2protocol);

		return protocol2party;
	}

	private static URI uri(String ref) {
		try {
			return new URI(ref);
		} catch (URISyntaxException e) {
			throw new IllegalStateException("failed to create basic URI", e);
		}
	}

	/**
	 * 
	 * @param classpath
	 * @return instance of the given {@link Party} on the classpath
	 * @throws IllegalArgumentException if the Party can not be instantiated, eg
	 *                                  because of a ClassCastException,
	 *                                  ClassNotFoundException,
	 *                                  IllegalAccessException etc. Such an
	 *                                  exception is considered a bug by the
	 *                                  programmer, because this is a
	 *                                  stand-alone runner.
	 */
	@SuppressWarnings("unchecked")
	private Party instantiate(String classpath) {
		System.out.println("Connecting with party '" + classpath + "'");
		Class<Party> partyclass;
		try {
			partyclass = (Class<Party>) Class.forName(classpath);
			Constructor<Party> ctor = partyclass.getConstructor();
			return ctor.newInstance(new Object[] {});
		} catch (ClassNotFoundException | NoSuchMethodException
				| SecurityException | InstantiationException
				| IllegalAccessException | IllegalArgumentException
				| InvocationTargetException e) {
			throw new IllegalArgumentException(
					"Failed to create party connection", e);
		}

	}

	private String getClassPath(URI uri) {
		if (!SCHEME.equals(uri.getScheme())) {
			throw new IllegalArgumentException("Required the " + SCHEME
					+ " protocol but found " + uri.getScheme());
		}
		String path = uri.getSchemeSpecificPart();
		if (path == null) {
			throw new IllegalArgumentException(
					"Expected classpath but found null  in " + uri);
		}
		return path;
	}

	@Override
	public List<ProtocolToPartyConn> connect(List<Reference> references)
			throws IOException, NoResourcesNowException {
		List<ProtocolToPartyConn> connections = new LinkedList<>();
		for (Reference partyref : references) {
			connections.add(connect(partyref));
		}
		return connections;
	}

}

class BasicConnectionWithParty extends BasicConnection<Action, Inform>
		implements ProtocolToPartyConn {

	private PartyId id;

	public BasicConnectionWithParty(Reference reference, URI uri) {
		super(reference, uri);
		this.id = new PartyId(uri.toString().replace("classpath:", "")
				.replaceAll("\\.", "_"));
	}

	@Override
	public PartyId getParty() {
		return id;
	}

}
