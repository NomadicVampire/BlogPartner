.. _faq_performance:

Performance
===========

.. contents::
    :local:
    :class: faq
    :backlinks: none

.. _faq_new_caching:

Why is my application slow after upgrading to 1.4 and/or 2.x?
--------------------------------------------------------------

SQLAlchemy as of version 1.4 includes a
:ref:`SQL compilation caching facility <sql_caching>` which will allow
Core and ORM SQL constructs to cache their stringified form, along with other
structural information used to fetch results from the statement, allowing the
relatively expensive string compilation process to be skipped when another
structurally equivalent construct is next used. This system
relies upon functionality that is implemented for all SQL constructs, including
objects such as  :class:`_schema.Column`,
:func:`_sql.select`, and :class:`_types.TypeEngine` objects, to produce a
**cache key** which fully represents their state to the degree that it affects
the SQL compilation process.

The caching system allows SQLAlchemy 1.4 and above to be more performant than
SQLAlchemy 1.3 with regards to the time spent converting SQL constructs into
strings repeatedly.  However, this only works if caching is enabled for the
dialect and SQL constructs in use; if not, string compilation is usually
similar to that of SQLAlchemy 1.3, with a slight decrease in speed in some
cases.

There is one case however where if SQLAlchemy's new caching system has been
disabled (for reasons below), performance for the ORM may be in fact
significantly poorer than that of 1.3 or other prior releases which is due to
the lack of caching within ORM lazy loaders and object refresh queries, which
in the 1.3 and earlier releases used the now-legacy ``BakedQuery`` system. If
an application is seeing significant (30% or higher) degradations in
performance (measured in time for operations to complete) when switching to
1.4, this is the likely cause of the issue, with steps to mitigate below.

.. seealso::

    :ref:`sql_caching` - overview of the caching system

    :ref:`caching_caveats` - additional information regarding the warnings
    generated for elements that don't enable caching.

Step one - turn on SQL logging and confirm whether or not caching is working
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Here, we want to use the technique described at
:ref:`engine logging <sql_caching_logging>`, looking for statements with the
``[no key]`` indicator or even ``[dialect does not support caching]``.
The indicators we would see for SQL statements that are successfully participating
in the caching system would be indicating ``[generated in Xs]`` when
statements are invoked for the first time and then
``[cached since Xs ago]`` for the vast majority of statements subsequent.
If ``[no key]`` is prevalent in particular for SELECT statements, or
if caching is disabled entirely due to ``[dialect does not support caching]``,
this can be the cause of significant performance degradation.

.. seealso::

    :ref:`sql_caching_logging`


Step two - identify what constructs are blocking caching from being enabled
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Assuming statements are not being cached, there should be warnings emitted
early in the application's log (SQLAlchemy 1.4.28 and above only) indicating
dialects, :class:`.TypeEngine` objects, and SQL constructs that are not
participating in caching.

For user defined datatypes such as those which extend :class:`_types.TypeDecorator`
and :class:`_types.UserDefinedType`, the warnings will look like::

    sqlalchemy.ext.SAWarning: MyType will not produce a cache key because the
    ``cache_ok`` attribute is not set to True. This can have significant
    performance implications including some performance degradations in
    comparison to prior SQLAlchemy versions. Set this attribute to True if this
    type object's state is safe to use in a cache key, or False to disable this
    warning.

For custom and third party SQL elements, such as those constructed using
the techniques described at :ref:`sqlalchemy.ext.compiler_toplevel`, these
warnings will look like::

    sqlalchemy.exc.SAWarning: Class MyClass will not make use of SQL
    compilation caching as it does not set the 'inherit_cache' attribute to
    ``True``. This can have significant performance implications including some
    performance degradations in comparison to prior SQLAlchemy versions. Set
    this attribute to True if this object can make use of the cache key
    generated by the superclass. Alternatively, this attribute may be set to
    False which will disable this warning.

For custom and third party dialects which make use of the :class:`.Dialect`
class hierarchy, the warnings will look like::

    sqlalchemy.exc.SAWarning: Dialect database:driver will not make use of SQL
    compilation caching as it does not set the 'supports_statement_cache'
    attribute to ``True``. This can have significant performance implications
    including some performance degradations in comparison to prior SQLAlchemy
    versions. Dialect maintainers should seek to set this attribute to True
    after appropriate development and testing for SQLAlchemy 1.4 caching
    support. Alternatively, this attribute may be set to False which will
    disable this warning.


Step three - enable caching for the given objects and/or seek alternatives
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Steps to mitigate the lack of caching include:

* Review and set :attr:`.ExternalType.cache_ok` to ``True`` for all custom types
  which extend from :class:`_types.TypeDecorator`,
  :class:`_types.UserDefinedType`, as well as subclasses of these such as
  :class:`_types.PickleType`.  Set this **only** if the custom type does not
  include any additional state attributes which affect how it renders SQL::

        class MyCustomType(TypeDecorator):
            cache_ok = True
            impl = String

  If the types in use are from a third-party library, consult with the
  maintainers of that library so that it may be adjusted and released.

  .. seealso::

    :attr:`.ExternalType.cache_ok` - background on requirements to enable
    caching for custom datatypes.

* Make sure third party dialects set :attr:`.Dialect.supports_statement_cache`
  to ``True``. What this indicates is that the maintainers of a third party
  dialect have made sure their dialect works with SQLAlchemy 1.4 or greater,
  and that their dialect doesn't include any compilation features which may get
  in the way of caching. As there are some common compilation patterns which
  can in fact interfere with caching, it's important that dialect maintainers
  check and test this carefully, adjusting for any of the legacy patterns
  which won't work with caching.

  .. seealso::

      :ref:`engine_thirdparty_caching` - background and examples for third-party
      dialects to participate in SQL statement caching.

* Custom SQL classes, including all DQL / DML constructs one might create
  using the :ref:`sqlalchemy.ext.compiler_toplevel`, as well as ad-hoc
  subclasses of objects such as :class:`_schema.Column` or
  :class:`_schema.Table`.   The :attr:`.HasCacheKey.inherit_cache` attribute
  may be set to ``True`` for trivial subclasses, which do not contain any
  subclass-specific state information which affects the SQL compilation.

  .. seealso::

    :ref:`compilerext_caching` - guidelines for applying the
    :attr:`.HasCacheKey.inherit_cache` attribute.


.. seealso::

    :ref:`sql_caching` - caching system overview

    :ref:`caching_caveats` - background on warnings emitted when caching
    is not enabled for specific constructs and/or dialects.


.. _faq_how_to_profile:

How can I profile a SQLAlchemy powered application?
---------------------------------------------------

Looking for performance issues typically involves two strategies.  One
is query profiling, and the other is code profiling.

Query Profiling
^^^^^^^^^^^^^^^

Sometimes just plain SQL logging (enabled via python's logging module
or via the ``echo=True`` argument on :func:`_sa.create_engine`) can give an
idea how long things are taking.  For example, if you log something
right after a SQL operation, you'd see something like this in your
log::

    17:37:48,325 INFO  [sqlalchemy.engine.base.Engine.0x...048c] SELECT ...
    17:37:48,326 INFO  [sqlalchemy.engine.base.Engine.0x...048c] {<params>}
    17:37:48,660 DEBUG [myapp.somemessage]

if you logged ``myapp.somemessage`` right after the operation, you know
it took 334ms to complete the SQL part of things.

Logging SQL will also illustrate if dozens/hundreds of queries are
being issued which could be better organized into much fewer queries.
When using the SQLAlchemy ORM, the "eager loading"
feature is provided to partially (:func:`.contains_eager()`) or fully
(:func:`_orm.joinedload()`, :func:`.subqueryload()`)
automate this activity, but without
the ORM "eager loading" typically means to use joins so that results across multiple
tables can be loaded in one result set instead of multiplying numbers
of queries as more depth is added (i.e. ``r + r*r2 + r*r2*r3`` ...)

For more long-term profiling of queries, or to implement an application-side
"slow query" monitor, events can be used to intercept cursor executions,
using a recipe like the following::

    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    import time
    import logging

    logging.basicConfig()
    logger = logging.getLogger("myapp.sqltime")
    logger.setLevel(logging.DEBUG)


    @event.listens_for(Engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.time())
        logger.debug("Start Query: %s", statement)


    @event.listens_for(Engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.time() - conn.info["query_start_time"].pop(-1)
        logger.debug("Query Complete!")
        logger.debug("Total Time: %f", total)

Above, we use the :meth:`_events.ConnectionEvents.before_cursor_execute` and
:meth:`_events.ConnectionEvents.after_cursor_execute` events to establish an interception
point around when a statement is executed.  We attach a timer onto the
connection using the :class:`._ConnectionRecord.info` dictionary; we use a
stack here for the occasional case where the cursor execute events may be nested.

.. _faq_code_profiling:

Code Profiling
^^^^^^^^^^^^^^

If logging reveals that individual queries are taking too long, you'd
need a breakdown of how much time was spent within the database
processing the query, sending results over the network, being handled
by the :term:`DBAPI`, and finally being received by SQLAlchemy's result set
and/or ORM layer.   Each of these stages can present their own
individual bottlenecks, depending on specifics.

For that you need to use the
`Python Profiling Module <https://docs.python.org/2/library/profile.html>`_.
Below is a simple recipe which works profiling into a context manager::

    import cProfile
    import io
    import pstats
    import contextlib


    @contextlib.contextmanager
    def profiled():
        pr = cProfile.Profile()
        pr.enable()
        yield
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats()
        # uncomment this to see who's calling what
        # ps.print_callers()
        print(s.getvalue())

To profile a section of code::

    with profiled():
        Session.query(FooClass).filter(FooClass.somevalue == 8).all()

The output of profiling can be used to give an idea where time is
being spent.   A section of profiling output looks like this::

    13726 function calls (13042 primitive calls) in 0.014 seconds

    Ordered by: cumulative time

    ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    222/21    0.001    0.000    0.011    0.001 lib/sqlalchemy/orm/loading.py:26(instances)
    220/20    0.002    0.000    0.010    0.001 lib/sqlalchemy/orm/loading.py:327(_instance)
    220/20    0.000    0.000    0.010    0.000 lib/sqlalchemy/orm/loading.py:284(populate_state)
       20    0.000    0.000    0.010    0.000 lib/sqlalchemy/orm/strategies.py:987(load_collection_from_subq)
       20    0.000    0.000    0.009    0.000 lib/sqlalchemy/orm/strategies.py:935(get)
        1    0.000    0.000    0.009    0.009 lib/sqlalchemy/orm/strategies.py:940(_load)
       21    0.000    0.000    0.008    0.000 lib/sqlalchemy/orm/strategies.py:942(<genexpr>)
        2    0.000    0.000    0.004    0.002 lib/sqlalchemy/orm/query.py:2400(__iter__)
        2    0.000    0.000    0.002    0.001 lib/sqlalchemy/orm/query.py:2414(_execute_and_instances)
        2    0.000    0.000    0.002    0.001 lib/sqlalchemy/engine/base.py:659(execute)
        2    0.000    0.000    0.002    0.001 lib/sqlalchemy/sql/elements.py:321(_execute_on_connection)
        2    0.000    0.000    0.002    0.001 lib/sqlalchemy/engine/base.py:788(_execute_clauseelement)

    ...

Above, we can see that the ``instances()`` SQLAlchemy function was called 222
times (recursively, and 21 times from the outside), taking a total of .011
seconds for all calls combined.

Execution Slowness
^^^^^^^^^^^^^^^^^^

The specifics of these calls can tell us where the time is being spent.
If for example, you see time being spent within ``cursor.execute()``,
e.g. against the DBAPI::

    2    0.102    0.102    0.204    0.102 {method 'execute' of 'sqlite3.Cursor' objects}

this would indicate that the database is taking a long time to start returning
results, and it means your query should be optimized, either by adding indexes
or restructuring the query and/or underlying schema.  For that task,
analysis of the query plan is warranted, using a system such as EXPLAIN,
SHOW PLAN, etc. as is provided by the database backend.

Result Fetching Slowness - Core
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If on the other hand you see many thousands of calls related to fetching rows,
or very long calls to ``fetchall()``, it may
mean your query is returning more rows than expected, or that the fetching
of rows itself is slow.   The ORM itself typically uses ``fetchall()`` to fetch
rows (or ``fetchmany()`` if the :meth:`_query.Query.yield_per` option is used).

An inordinately large number of rows would be indicated
by a very slow call to ``fetchall()`` at the DBAPI level::

    2    0.300    0.600    0.300    0.600 {method 'fetchall' of 'sqlite3.Cursor' objects}

An unexpectedly large number of rows, even if the ultimate result doesn't seem
to have many rows, can be the result of a cartesian product - when multiple
sets of rows are combined together without appropriately joining the tables
together.   It's often easy to produce this behavior with SQLAlchemy Core or
ORM query if the wrong :class:`_schema.Column` objects are used in a complex query,
pulling in additional FROM clauses that are unexpected.

On the other hand, a fast call to ``fetchall()`` at the DBAPI level, but then
slowness when SQLAlchemy's :class:`_engine.CursorResult` is asked to do a ``fetchall()``,
may indicate slowness in processing of datatypes, such as unicode conversions
and similar::

    # the DBAPI cursor is fast...
    2    0.020    0.040    0.020    0.040 {method 'fetchall' of 'sqlite3.Cursor' objects}

    ...

    # but SQLAlchemy's result proxy is slow, this is type-level processing
    2    0.100    0.200    0.100    0.200 lib/sqlalchemy/engine/result.py:778(fetchall)

In some cases, a backend might be doing type-level processing that isn't
needed.   More specifically, seeing calls within the type API that are slow
are better indicators - below is what it looks like when we use a type like
this::

    from sqlalchemy import TypeDecorator
    import time


    class Foo(TypeDecorator):
        impl = String

        def process_result_value(self, value, thing):
            # intentionally add slowness for illustration purposes
            time.sleep(0.001)
            return value

the profiling output of this intentionally slow operation can be seen like this::

      200    0.001    0.000    0.237    0.001 lib/sqlalchemy/sql/type_api.py:911(process)
      200    0.001    0.000    0.236    0.001 test.py:28(process_result_value)
      200    0.235    0.001    0.235    0.001 {time.sleep}

that is, we see many expensive calls within the ``type_api`` system, and the actual
time consuming thing is the ``time.sleep()`` call.

Make sure to check the :ref:`Dialect documentation <dialect_toplevel>`
for notes on known performance tuning suggestions at this level, especially for
databases like Oracle.  There may be systems related to ensuring numeric accuracy
or string processing that may not be needed in all cases.

There also may be even more low-level points at which row-fetching performance is suffering;
for example, if time spent seems to focus on a call like ``socket.receive()``,
that could indicate that everything is fast except for the actual network connection,
and too much time is spent with data moving over the network.

Result Fetching Slowness - ORM
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To detect slowness in ORM fetching of rows (which is the most common area
of performance concern), calls like ``populate_state()`` and ``_instance()`` will
illustrate individual ORM object populations::

    # the ORM calls _instance for each ORM-loaded row it sees, and
    # populate_state for each ORM-loaded row that results in the population
    # of an object's attributes
    220/20    0.001    0.000    0.010    0.000 lib/sqlalchemy/orm/loading.py:327(_instance)
    220/20    0.000    0.000    0.009    0.000 lib/sqlalchemy/orm/loading.py:284(populate_state)

The ORM's slowness in turning rows into ORM-mapped objects is a product
of the complexity of this operation combined with the overhead of cPython.
Common strategies to mitigate this include:

* fetch individual columns instead of full entities, that is::

      session.query(User.id, User.name)

  instead of::

      session.query(User)

* Use :class:`.Bundle` objects to organize column-based results::

      u_b = Bundle('user', User.id, User.name)
      a_b = Bundle('address', Address.id, Address.email)

      for user, address in session.query(u_b, a_b).join(User.addresses):
          # ...

* Use result caching - see :ref:`examples_caching` for an in-depth example
  of this.

* Consider a faster interpreter like that of PyPy.

The output of a profile can be a little daunting but after some
practice they are very easy to read.

.. seealso::

    :ref:`examples_performance` - a suite of performance demonstrations
    with bundled profiling capabilities.

I'm inserting 400,000 rows with the ORM and it's really slow!
-------------------------------------------------------------

The SQLAlchemy ORM uses the :term:`unit of work` pattern when synchronizing
changes to the database. This pattern goes far beyond simple "inserts"
of data. It includes that attributes which are assigned on objects are
received using an attribute instrumentation system which tracks
changes on objects as they are made, includes that all rows inserted
are tracked in an identity map which has the effect that for each row
SQLAlchemy must retrieve its "last inserted id" if not already given,
and also involves that rows to be inserted are scanned and sorted for
dependencies as needed. Objects are also subject to a fair degree of
bookkeeping in order to keep all of this running, which for a very
large number of rows at once can create an inordinate amount of time
spent with large data structures, hence it's best to chunk these.

Basically, unit of work is a large degree of automation in order to
automate the task of persisting a complex object graph into a
relational database with no explicit persistence code, and this
automation has a price.

ORMs are basically not intended for high-performance bulk inserts -
this is the whole reason SQLAlchemy offers the Core in addition to the
ORM as a first-class component.

For the use case of fast bulk inserts, the
SQL generation and execution system that the ORM builds on top of
is part of the :ref:`Core <sqlexpression_toplevel>`.  Using this system directly, we can produce an INSERT that
is competitive with using the raw database API directly.

.. note::

    When using the psycopg2 dialect, consider making use of the :ref:`batch
    execution helpers <psycopg2_executemany_mode>` feature of psycopg2, now
    supported directly by the SQLAlchemy psycopg2 dialect.

Alternatively, the SQLAlchemy ORM offers the :ref:`bulk_operations`
suite of methods, which provide hooks into subsections of the unit of
work process in order to emit Core-level INSERT and UPDATE constructs with
a small degree of ORM-based automation.

The example below illustrates time-based tests for several different
methods of inserting rows, going from the most automated to the least.
With cPython, runtimes observed::

    Python: 3.8.12 | packaged by conda-forge | (default, Sep 29 2021, 19:42:05)  [Clang 11.1.0 ]
    sqlalchemy v1.4.22 (future=True)
    SQLA ORM:
            Total time for 100000 records 5.722 secs
    SQLA ORM pk given:
            Total time for 100000 records 3.781 secs
    SQLA ORM bulk_save_objects:
            Total time for 100000 records 1.385 secs
    SQLA ORM bulk_save_objects, return_defaults:
            Total time for 100000 records 3.858 secs
    SQLA ORM bulk_insert_mappings:
            Total time for 100000 records 0.472 secs
    SQLA ORM bulk_insert_mappings, return_defaults:
            Total time for 100000 records 2.840 secs
    SQLA Core:
            Total time for 100000 records 0.246 secs
    sqlite3:
            Total time for 100000 records 0.153 secs

We can reduce the time by a factor of nearly three using recent versions of `PyPy <https://pypy.org/>`_::

    Python: 3.7.10 | packaged by conda-forge | (77787b8f, Sep 07 2021, 14:06:31) [PyPy 7.3.5 with GCC Clang 11.1.0]
    sqlalchemy v1.4.25 (future=True)
    SQLA ORM:
            Total time for 100000 records 2.976 secs
    SQLA ORM pk given:
            Total time for 100000 records 1.676 secs
    SQLA ORM bulk_save_objects:
            Total time for 100000 records 0.658 secs
    SQLA ORM bulk_save_objects, return_defaults:
            Total time for 100000 records 1.158 secs
    SQLA ORM bulk_insert_mappings:
            Total time for 100000 records 0.403 secs
    SQLA ORM bulk_insert_mappings, return_defaults:
            Total time for 100000 records 0.976 secs
    SQLA Core:
            Total time for 100000 records 0.241 secs
    sqlite3:
            Total time for 100000 records 0.128 secs

Script::

    import contextlib
    import sqlite3
    import sys
    import tempfile
    import time

    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy import __version__, Column, Integer, String, create_engine, insert
    from sqlalchemy.orm import Session

    Base = declarative_base()


    class Customer(Base):
        __tablename__ = "customer"
        id = Column(Integer, primary_key=True)
        name = Column(String(255))


    @contextlib.contextmanager
    def sqlalchemy_session(future):
        with tempfile.NamedTemporaryFile(suffix=".db") as handle:
            dbpath = handle.name
            engine = create_engine(f"sqlite:///{dbpath}", future=future, echo=False)
            session = Session(
                bind=engine, future=future, autoflush=False, expire_on_commit=False
            )
            Base.metadata.create_all(engine)
            yield session
            session.close()


    def print_result(name, nrows, seconds):
        print(f"{name}:\n{' '*10}Total time for {nrows} records {seconds:.3f} secs")


    def test_sqlalchemy_orm(n=100000, future=True):
        with sqlalchemy_session(future) as session:
            t0 = time.time()
            for i in range(n):
                customer = Customer()
                customer.name = "NAME " + str(i)
                session.add(customer)
                if i % 1000 == 0:
                    session.flush()
            session.commit()
            print_result("SQLA ORM", n, time.time() - t0)


    def test_sqlalchemy_orm_pk_given(n=100000, future=True):
        with sqlalchemy_session(future) as session:
            t0 = time.time()
            for i in range(n):
                customer = Customer(id=i + 1, name="NAME " + str(i))
                session.add(customer)
                if i % 1000 == 0:
                    session.flush()
            session.commit()
            print_result("SQLA ORM pk given", n, time.time() - t0)


    def test_sqlalchemy_orm_bulk_save_objects(n=100000, future=True, return_defaults=False):
        with sqlalchemy_session(future) as session:
            t0 = time.time()
            for chunk in range(0, n, 10000):
                session.bulk_save_objects(
                    [
                        Customer(name="NAME " + str(i))
                        for i in range(chunk, min(chunk + 10000, n))
                    ],
                    return_defaults=return_defaults,
                )
            session.commit()
            print_result(
                f"SQLA ORM bulk_save_objects{', return_defaults' if return_defaults else ''}",
                n,
                time.time() - t0,
            )


    def test_sqlalchemy_orm_bulk_insert(n=100000, future=True, return_defaults=False):
        with sqlalchemy_session(future) as session:
            t0 = time.time()
            for chunk in range(0, n, 10000):
                session.bulk_insert_mappings(
                    Customer,
                    [
                        dict(name="NAME " + str(i))
                        for i in range(chunk, min(chunk + 10000, n))
                    ],
                    return_defaults=return_defaults,
                )
            session.commit()
            print_result(
                f"SQLA ORM bulk_insert_mappings{', return_defaults' if return_defaults else ''}",
                n,
                time.time() - t0,
            )


    def test_sqlalchemy_core(n=100000, future=True):
        with sqlalchemy_session(future) as session:
            with session.bind.begin() as conn:
                t0 = time.time()
                conn.execute(
                    insert(Customer.__table__),
                    [{"name": "NAME " + str(i)} for i in range(n)],
                )
                conn.commit()
                print_result("SQLA Core", n, time.time() - t0)


    @contextlib.contextmanager
    def sqlite3_conn():
        with tempfile.NamedTemporaryFile(suffix=".db") as handle:
            dbpath = handle.name
            conn = sqlite3.connect(dbpath)
            c = conn.cursor()
            c.execute("DROP TABLE IF EXISTS customer")
            c.execute(
                "CREATE TABLE customer (id INTEGER NOT NULL, "
                "name VARCHAR(255), PRIMARY KEY(id))"
            )
            conn.commit()
            yield conn


    def test_sqlite3(n=100000):
        with sqlite3_conn() as conn:
            c = conn.cursor()
            t0 = time.time()
            for i in range(n):
                row = ("NAME " + str(i),)
                c.execute("INSERT INTO customer (name) VALUES (?)", row)
            conn.commit()
            print_result("sqlite3", n, time.time() - t0)


    if __name__ == "__main__":
        rows = 100000
        _future = True
        print(f"Python: {' '.join(sys.version.splitlines())}")
        print(f"sqlalchemy v{__version__} (future={_future})")
        test_sqlalchemy_orm(rows, _future)
        test_sqlalchemy_orm_pk_given(rows, _future)
        test_sqlalchemy_orm_bulk_save_objects(rows, _future)
        test_sqlalchemy_orm_bulk_save_objects(rows, _future, True)
        test_sqlalchemy_orm_bulk_insert(rows, _future)
        test_sqlalchemy_orm_bulk_insert(rows, _future, True)
        test_sqlalchemy_core(rows, _future)
        test_sqlite3(rows)
