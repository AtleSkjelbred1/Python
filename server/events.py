"""In-process pub/sub hub used to push server-sent events to clients."""
import json
import queue
import threading

_subscribers = []
_lock = threading.Lock()


def subscribe():
    q = queue.Queue()
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q):
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)


def publish(event_type: str, data: dict):
    message = json.dumps(data)
    with _lock:
        targets = list(_subscribers)
    for q in targets:
        q.put((event_type, message))


def stream(q):
    try:
        while True:
            event_type, message = q.get()
            yield f"event: {event_type}\ndata: {message}\n\n"
    finally:
        unsubscribe(q)
