from time import time, sleep
from beetsplug.drop2beets import Drop2BeetsHandler

def test_debounce():
    handler = Drop2BeetsHandler(None)
    handler.forget_debounce()
    assert len(handler.debounce) == 0

    handler.debounce["some/song.flac"] = 1692542424 # time of writing this test
    handler.debounce["new_song.flac"] = time()
    handler.forget_debounce()
    assert len(handler.debounce) == 1
    sleep(Drop2BeetsHandler.DEBOUNCE_WINDOW + 0.01)
    handler.forget_debounce()
    assert len(handler.debounce) == 0

