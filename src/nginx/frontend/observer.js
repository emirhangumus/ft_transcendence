/**
       * The core of reactive programming is the signal function.
       */
let activeObserver = null;

const signal = (value) => {
  let _value = value;
  const _subscribers = new Set();

  function unlink(dep) {
    _subscribers.delete(dep);
  }

  function read() {
    if (activeObserver && !_subscribers.has(activeObserver)) {
      _subscribers.add(activeObserver);
      activeObserver.link(unlink);
    }

    return _value;
  }

  function write(valueOrFn) {
    const newValue =
      typeof valueOrFn === "function" ? valueOrFn(_value) : valueOrFn;
    if (newValue === _value) return;
    _value = newValue;

    for (const subscriber of [..._subscribers]) {
      subscriber.notify();
    }
  }

  return [read, write];
};

const effect = (cb, deps) => {
  let _externalCleanup; // defined explicitly by user
  let _unlinkSubscriptions = new Set(); // track active signals (to unlink on re-run)

  const effectInstance = { notify: execute, link };

  function link(unlink) {
    _unlinkSubscriptions.add(unlink);
  }

  function execute() {
    dispose();
    activeObserver = effectInstance;
    _externalCleanup = cb();
    activeObserver = null;
  }

  function dispose() {
    for (const unlink of _unlinkSubscriptions) {
      unlink(effectInstance);
    }
    _unlinkSubscriptions.clear();

    if (typeof _externalCleanup === "function") {
      _externalCleanup();
    }
  }

  execute();

  return dispose;
};