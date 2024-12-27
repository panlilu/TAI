from redis import Redis
from rq import Worker, Queue

listen = ['default']

redis_conn = Redis()

if __name__ == '__main__':
    queues = [Queue(name, connection=redis_conn) for name in listen]
    worker = Worker(queues, connection=redis_conn)
    worker.work()
