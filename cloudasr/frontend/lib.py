import zmq
import re
from cloudasr.messages import WorkerRequestMessage, MasterResponseMessage, RecognitionRequestMessage, ResultsMessage

def create_frontend_worker(master_address):
    context = zmq.Context()
    master_socket = context.socket(zmq.REQ)
    master_socket.connect(master_address)
    worker_socket = context.socket(zmq.REQ)

    return FrontendWorker(master_socket, worker_socket)


class FrontendWorker:
    def __init__(self, master_socket, worker_socket):
        self.master_socket = master_socket
        self.worker_socket = worker_socket

    def recognize_batch(self, data, headers):
        self.validate_headers(headers)
        self.connect_to_worker(data["model"])
        response = self.recognize_batch_on_worker(data)

        return response

    def connect_to_worker(self, model):
        self.worker_address = self.get_worker_address_from_master(model)
        self.worker_socket.connect(self.worker_address)

    def validate_headers(self, headers):
        if "Content-Type" not in headers:
            raise MissingHeaderError()

        if not re.match("audio/x-wav; rate=\d+;", headers["Content-Type"]):
            raise MissingHeaderError()

    def get_worker_address_from_master(self, model):
        request = WorkerRequestMessage()
        request.model = model

        self.master_socket.send(request.SerializeToString())
        response = MasterResponseMessage()
        response.ParseFromString(self.master_socket.recv())

        if response.status == MasterResponseMessage.SUCCESS:
            return response.address
        else:
            raise NoWorkerAvailableError()

    def recognize_batch_on_worker(self, data):
        message = RecognitionRequestMessage()
        message.body = data["wav"]
        message.type = RecognitionRequestMessage.BATCH

        self.worker_socket.send(message.SerializeToString())
        response = ResultsMessage()
        response.ParseFromString(self.worker_socket.recv())

        self.worker_socket.disconnect(self.worker_address)

        return self.format_response(response)

    def format_response(self, response):
        return {
            "result": [
                {
                    "alternative": [{"confidence": a.confidence, "transcript": a.transcript} for a in response.alternatives],
                    "final": response.final,
                },
            ],
            "result_index": 0,
        }

class NoWorkerAvailableError(Exception):
    pass

class MissingHeaderError(Exception):
    pass
