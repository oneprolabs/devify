# Database

Select the database engine with `DB_ENGINE`. Both compose stacks ship a
**MariaDB** service, so the recommended setup is `DB_ENGINE=mysql` with
`MYSQL_HOST=mysql` (the service name).

## Engines

| Engine | Variables |
|--------|-----------|
| `sqlite` | `SQLITE_PATH` |
| `mysql` | `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_ROOT_PASSWORD` |
| `postgresql` | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` |

## Recommended (MySQL / MariaDB)

```dotenv
DB_ENGINE=mysql
MYSQL_USER=devify
MYSQL_PASSWORD=devify
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=devify
MYSQL_ROOT_PASSWORD=devify_root
```

> The bundled MariaDB container **requires `MYSQL_ROOT_PASSWORD`**. If it is
> unset, the container crash-loops with *"Database is uninitialized and password
> option is not specified"* and the API never starts (it waits on the database's
> health check). Use strong passwords in production.

## SQLite

`DB_ENGINE=sqlite` with `SQLITE_PATH` works for quick trials, but the compose
stacks are built around the MariaDB service — prefer MySQL for any real
deployment.
