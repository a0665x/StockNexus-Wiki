# CodeGraph access

The indexed root is the StockNexus-Wiki checkout. It includes the Python service, JavaScript frontend under `dist/`, Chat bridge and tests. Runtime databases, vendor scripts and minified bundles are excluded. The local SQLite index stays in the checkout's ignored `.codegraph/` directory. [Project configuration](../../codegraph.json)

## Starting a task

Read the project map and latest handoff. With an existing index, call `codegraph_explore` with the absolute checkout path as `projectPath` and name the feature or symbol. From the repository root, the corresponding CLI query for the shared header is:

```sh
codegraph explore 'initHeaderResize frameBrand initFloatingPanel' --max-files 2
```

Follow the returned paths to the current implementation and its browser journey. HTML and CSS geometry also needs a browser measurement. [Feature-to-test index](../TESTING.md#workbench-release-verification) · [Architecture](../ARCHITECTURE.md)

For tooltip timing or dismissal, `codegraph explore 'dist/workbench-help.js helpAt' --max-files 1` locates the shared controller. Its browser interactions are driven through the DOM. Use the [contextual help journey](../../tests/browser_workbench_help.py) to follow them.

## Index health

`codegraph status --strict .` checks freshness. The MCP watcher updates the local index for changed files. With a CLI-only session, `codegraph sync .` refreshes an existing index incrementally. If an open MCP connection reports `statInode is not a function`, reconnect it or use the installed CLI. A fresh MCP connection and the CLI both returned the header symbols during release verification. A separate checkout starts without this local database. Use scoped source search there until the user requests indexing.
