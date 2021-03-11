package geniusweb.simplerunner;

import static org.junit.Assert.assertNotNull;

import java.io.IOException;
import java.net.URISyntaxException;

import org.junit.Before;
import org.junit.Test;

import geniusweb.actions.Action;
import geniusweb.connection.ConnectionEnd;
import geniusweb.inform.Inform;
import geniusweb.references.PartyRef;

public class ClassPathConnectionFactoryTest {
	private ClassPathConnectionFactory factory;

	@Before
	public void before() {
		factory = new ClassPathConnectionFactory();

	}

	@Test(expected = IllegalArgumentException.class)
	public void testWrongURI() throws IOException, URISyntaxException {
		factory.connect(new PartyRef("http://blabla"));
	}

	@Test(expected = IllegalArgumentException.class)
	public void testNullPath() throws IOException, URISyntaxException {
		// bad because classpath should not start with //
		factory.connect(new PartyRef("http://some.class.path"));
	}

	@Test(expected = IllegalArgumentException.class)
	public void testUnknownParty() throws IOException, URISyntaxException {
		factory.connect(new PartyRef("classpath:blabla.bla"));
	}

	@Test
	public void testRandomParty() throws IOException, URISyntaxException {
		ConnectionEnd<Action, Inform> party = factory.connect(new PartyRef(
				"classpath:geniusweb.exampleparties.randomparty.RandomParty"));
		assertNotNull(party);
	}

}
