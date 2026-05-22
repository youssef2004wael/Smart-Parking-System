import threading
import queue
import torch


class GPUWorker(threading.Thread):

    def __init__(self, device=0):
        super().__init__(daemon=True)
        self.tasks = queue.Queue()
        self.running = True
        self.device = device

    def submit(self, func, *args, **kwargs):
        result_queue = queue.Queue(maxsize=1)
        self.tasks.put((func, args, kwargs, result_queue))
        return result_queue

    def run(self):
        torch.cuda.set_device(self.device)

        while self.running:
            func, args, kwargs, result_queue = self.tasks.get()
            try:
                with torch.no_grad():
                    result = func(*args, **kwargs)
                result_queue.put(result)
            except Exception as e:
                result_queue.put(e)


# =========================
# GLOBAL SINGLETONS
# =========================

_gpu_worker = None
_entrance_worker = None
_lock = threading.Lock()


def get_gpu_worker():
    global _gpu_worker
    if _gpu_worker is None:
        with _lock:
            if _gpu_worker is None:
                _gpu_worker = GPUWorker(device=0)
                _gpu_worker.start()
    return _gpu_worker


def get_entrance_worker():
    global _entrance_worker
    if _entrance_worker is None:
        with _lock:
            if _entrance_worker is None:
                _entrance_worker = GPUWorker(device=0)
                _entrance_worker.start()
    return _entrance_worker