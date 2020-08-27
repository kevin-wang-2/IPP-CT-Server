import multiprocessing
import function.setup

if __name__ == "__main__":
    config, garage_id = function.setup.setup()
    if garage_id is None:
        exit(1)
    assert (len(config["hardware"]["drone"]) < multiprocessing.cpu_count())

