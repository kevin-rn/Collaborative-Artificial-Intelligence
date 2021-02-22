package geniusweb.simplerunner;

import java.io.IOException;
import java.net.URI;
import java.util.concurrent.ArrayBlockingQueue;

import geniusweb.connection.ConnectionEnd;
import geniusweb.references.Reference;
import tudelft.utilities.listener.DefaultListenable;
import tudelft.utilities.listener.Listener;

/**
 * A basic connection that implements connection with direct calls
 * 
 *
 * @param <IN>  the type of the incoming data
 * @param <OUT> the type of outgoing data
 */
public class BasicConnection<IN, OUT> extends DefaultListenable<IN>
		implements ConnectionEnd<IN, OUT> {
	private final Reference reference;
	private final URI uri;
	// to be initialized
	private Listener<OUT> handler = null;
	private Thread handlerThread;
	private ArrayBlockingQueue<OUT> messages = new ArrayBlockingQueue<OUT>(4);

	/**
	 * 
	 * @param reference Reference that was used to create this connection.
	 * @param uri       the URI of the remote endpoint that makes up the
	 *                  connection. This is a URI that uniquely identifies the
	 *                  remote object
	 */
	public BasicConnection(Reference reference, URI uri) {
		this.reference = reference;
		this.uri = uri;

	}

	/**
	 * To be called to hook up the other side that will handle a send action
	 * from us. Must be called first.
	 * 
	 * @param newhandler a Listener&lt;OUT&gt; that can handle send actions.
	 * 
	 */
	public void init(Listener<OUT> newhandler) {
		if (handler != null) {
			throw new IllegalStateException("already initialized");
		}
		this.handler = newhandler;

		handlerThread = new Thread(new Runnable() {

			@Override
			public void run() {
				try {
					while (true) {
						handler.notifyChange(messages.take());
					}
				} catch (InterruptedException e) {
					System.out.println("connection handler interrupted");
				}
			}
		});

		handlerThread.start();
	}

	@Override
	public void send(OUT data) throws IOException {
		if (handler == null) {
			throw new IllegalStateException(
					"BasicConnection has not been initialized");
		}
		try {
			messages.put(data);
		} catch (InterruptedException e) {
			throw new IOException(e);
		}
	}

	@Override
	public Reference getReference() {
		return reference;
	}

	@Override
	public URI getRemoteURI() {
		return uri;
	}

	@Override
	public void close() {
		handlerThread.interrupt();
		handlerThread = null;
		handler = null;
	}

	@Override
	public Error getError() {
		return null;
	}

}
