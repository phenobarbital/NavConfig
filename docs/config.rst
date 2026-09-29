Config
========

``mredis``
-------------

.. autofunction:: navconfig.config.mredis


``mcache``
-------------

.. autofunction:: navconfig.config.mcache


``Singleton``
--------------

.. autofunction:: navconfig.config.Singleton


``navigatorConfig``
-------------------

.. autofunction:: navconfig.config.navigatorConfig

Vault document cache and async API
----------------------------------

Every read from HashiCorp Vault goes through a process-wide cache of whole KV
documents, keyed by ``(url, token, mount, version, path)``. A key is therefore
fetched with at most one remote read per path within the TTL, and all
``VaultReader`` instances (including the one used by ``vaultLoader``) share it.

``VAULT_CACHE_TTL``
    Cache lifetime in seconds (float). Default ``300``. ``0`` means entries
    never expire (a negative value behaves the same). It is read once, when
    the cache is first used; an unparsable value logs a warning and falls
    back to ``300``. The Vault URL is normalized (trailing ``/`` ignored)
    when building the cache key.

Negative caching
    A path that does not exist is cached too, so a secret created directly in
    Vault stays invisible until the TTL expires, ``set()`` is called, or the
    cache is invalidated. Transient errors are never cached.

Returned values
    ``get()`` and ``list()`` return deep copies, so mutating a result never
    changes the cached document. ``set()``/``delete()`` hold a per-path lock
    across read-modify-write and cache update, so concurrent writers cannot
    leave the cache different from Vault.

Invalidation
    ``config.invalidate_vault_cache(path=None)`` drops cached documents
    (one path, or all). ``config.reload_current_env()`` invalidates the cache
    before reloading. ``VaultReader.invalidate()`` and ``VaultReader.refresh()``
    do the same at reader level.

Async API
    Vault I/O runs in worker threads (``asyncio.to_thread``), so it does not
    block the event loop::

        # prefetch concurrently from an on_startup handler
        await config.aload_vault(["myenv", "shared"])   # {path: found}

        # afterwards, sync config.get() performs no remote read
        value = await config.aget("KEY")
        present = await config.aexists("KEY")

    The async methods use ``asyncio.to_thread`` (the default executor). Many
    concurrent callers waiting on the *same* uncached path occupy one worker
    thread each, so prefetch with ``aload_vault`` at startup instead of
    fanning out ``aget`` calls on a cold cache.
