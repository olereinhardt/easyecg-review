import json
import threading
from http.server import BaseHTTPRequestHandler,HTTPServer
import pytest
from easyecg_review.ai import ai_review
from easyecg_review.cli import load_config,main


def test_remote_requires_explicit_optin(tmp_path):
    context=tmp_path/'context.json';context.write_text('{"schema":"easyecg-review-ai-context-v1"}')
    with pytest.raises(ValueError,match='--allow-remote'):
        ai_review(context,tmp_path/'out.md','model','https://example.org/api/generate')


def test_local_ai_mock(tmp_path):
    context=tmp_path/'context.json';context.write_text('{"schema":"easyecg-review-ai-context-v1"}')
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(request);self.send_response(200);self.end_headers();self.wfile.write(b'{"response":"Mock review only"}')
        def log_message(self,*args):pass
    server=HTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:ai_review(context,tmp_path/'out.md','model',f'http://127.0.0.1:{server.server_port}/api/generate')
    finally:server.shutdown();server.server_close();thread.join()
    assert requests[0]['stream'] is False
    assert 'NOT a validated' in requests[0]['prompt']
    assert 'UNVALIDIERTER' in (tmp_path/'out.md').read_text()


def test_unknown_config_rejected(tmp_path):
    p=tmp_path/'config.json';p.write_text('{"nonsense":2}')
    with pytest.raises(ValueError):load_config(p)
    p.write_text('{"quality_window_s":5}')
    with pytest.raises(ValueError):load_config(p)


def test_cli_missing_input_does_not_create_output(tmp_path):
    assert main(['run',str(tmp_path/'absent'),'-o',str(tmp_path/'out')])==2
    assert not (tmp_path/'out').exists()


def test_ai_redirect_not_followed(tmp_path):
    context=tmp_path/'context.json';context.write_text('{"schema":"easyecg-review-ai-context-v1"}')
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(307);self.send_header('Location','https://example.org/api/generate');self.end_headers()
        def log_message(self,*args):pass
    server=HTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with pytest.raises(ValueError,match='redirects'):
            ai_review(context,tmp_path/'out.md','model',f'http://127.0.0.1:{server.server_port}/api/generate')
    finally:server.shutdown();server.server_close();thread.join()
    assert not (tmp_path/'out.md').exists()
