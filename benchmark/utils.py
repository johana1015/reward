import multiprocessing
import multiprocessing.pool
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import style
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

import reward.utils as U

style.use("ggplot")


class NoDaemonProcess(multiprocessing.Process):
    """
    Run process inside processes, from:
    https://stackoverflow.com/questions/6974695/python-process-pool-non-daemonic.
    """

    def _get_daemon(self):
        return False

    def _set_daemon(self, value):
        pass

    daemon = property(_get_daemon, _set_daemon)


class NoDaemonProcessPool(multiprocessing.pool.Pool):
    Process = NoDaemonProcess


def get_initials(s):
    if s == "lr" or s == "eps":
        return s
    else:
        return "".join(w[0] for w in s.split("_"))


def bool2str(x, suffix):
    return ["d", ""][int(x)] + get_initials(suffix)


def dict2str(d):
    return "_".join(get_initials(k) + str(v) for k, v in d.items())


def config2str(config):
    tags = []
    trial = config.pop("trial")

    for k, v in config.items():
        if k == "env_name":
            continue
        elif isinstance(v, bool):
            tags.append(bool2str(v, k))
        elif isinstance(v, dict):
            tags.append("{}({})".format(get_initials(k), dict2str(v)))
        elif isinstance(v, U.estimators.BaseEstimator):
            tags.append("{}({})".format(v.__class__.__name__, dict2str(v.__dict__)))
        elif k == "activation":
            tags.append(v.__name__)
        else:
            tags.append(get_initials(k) + str(v))
    tags.append("t{}".format(trial))

    return "-".join(tags)


def read_tf_event(file_path):
    # print('Reading: {}'.format(file_path))
    event_acc = EventAccumulator(str(file_path))
    event_acc.Reload()
    data = {}

    for tag in event_acc.Tags()["scalars"]:
        _, data["steps"], data[tag] = zip(*event_acc.Scalars(tag))

    steps = data.pop("steps")

    min_len = min([len(v) for v in data.values()])
    data = {k: v[:min_len] for k, v in data.items()}
    df = pd.DataFrame(data)
    df.insert(0, "Steps", steps[:min_len])
    return df


def get_logs(log_dir, tag):
    log_dir = Path(log_dir)
    tag += "*"
    files_path = [list(p.glob("events.out.tfevents.*"))[0] for p in log_dir.glob(tag)]

    runs = {}
    for i, f in enumerate(files_path):
        runs[i] = read_tf_event(f)

    return pd.Panel(runs)


def plot_panel(panel, column, ax=None, label=None, window=10):
    if ax is None:
        fig, ax = plt.subplots()

    steps = panel[0]["Steps"]
    panel_mean = panel.mean(0)[column].rolling(window).mean()
    panel_min = panel.min(0)[column].rolling(window).mean()
    panel_max = panel.max(0)[column].rolling(window).mean()

    ax.plot(steps, panel_mean, label=label)
    ax.fill_between(steps, panel_min, panel_max, alpha=0.1)
    ax.set_title(column)
    leg = ax.legend(fancybox=True)
    leg.get_frame().set_alpha(0.3)


def plot_logs(log_dir, tags, window=10):
    fig = None
    for tag in tags:
        panel = get_logs(log_dir=log_dir, tag=tag)
        columns = list(panel[0].columns)

        if fig is None:
            fig, axs = plt.subplots(
                len(columns) - 1, 1, figsize=(16, (len(columns) - 1) * 10)
            )
            # Set non-repeating colors
            for ax in axs.flat:
                ax.set_prop_cycle(
                    "color", plt.cm.gist_ncar(np.linspace(0, 1, len(tags)))
                )

        i = 0
        for column in columns:
            if column == "Steps":
                continue
            plot_panel(panel, column=column, ax=axs.flat[i], label=tag, window=window)
            i += 1
