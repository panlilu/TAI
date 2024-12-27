import os
from redis import Redis
from rq import Worker, Queue

# 设置MacOS上的fork安全环境变量
os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'

listen = ['default']

redis_conn = Redis()

if __name__ == '__main__':
    queues = [Queue(name, connection=redis_conn) for name in listen]
    worker = Worker(queues, connection=redis_conn)
    worker.work()
