# Source SDK validation

Run on Linux x86-64 with Node.js 22, Python 3, curl, tar/xz, make and a C compiler:

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run test:negative
```

The first run downloads the original Unity Linux archive (about 3 GB), extracts
only its managed compiler, .NET runtime and references, and builds Lua 5.1.5.
Subsequent runs reuse `.sdk-tools/`. No editor is launched and no Unity activation,
account, backend connection or registry credential is used. Versions, original
URLs and SHA-256 digests live in [`scripts/tools.json`](../scripts/tools.json);
TypeScript is locked in [`package-lock.json`](../package-lock.json). CI caches
extracted tools, not the large archive. Delete `.sdk-tools/` for a fresh bootstrap.

## What the check proves

`SDK checks` runs without path filters on pull requests, merge queue groups and
pushes to `main`, on self-hosted runners. Its `ci-ok` job always runs after
`sdk-checks` and uses the shared fail-closed dependency verdict. A failed,
cancelled, skipped or absent producer cannot pass `ci-ok`. The shared action also
checks contribution metadata and added commits for secrets. Required-check
settings are a separate control, not a workflow claim.

| Package | Compilation and consumer proof |
| --- | --- |
| Unity | `npm pack --ignore-scripts` creates a local UPM tarball from the existing manifest. All source and `.meta` bytes must survive extraction unchanged. Original Unity 2022.3.0f1 Roslyn and unmodified Unity references compile unpacked source for player, Android, iOS and editor conditional branches. Separate consumers compile against each assembly's public API. Engine-independent `SdkConfig` tests execute on Unity's bundled .NET runtime. Assembly references, asset metadata and package identity are checked. |
| Cocos Creator | Both unpacked TypeScript modules and a separate importing consumer compile in strict mode against generated declarations from the official Creator 2.4.4 benchmark project. Node tests consume the emitted SDK module and exercise anonymous auth, event requests, persisted identities, migration success and migration failure fallback. |
| Solar2D | Lua 5.1.5 compiles both unpacked modules and the consumer. The consumer loads the actual modules with Solar2D's original JSON implementation and exercises initialization, event requests, session lifecycle, remote config and persisted identity reuse. |

Cocos and Solar2D tests replace host storage/HTTP/lifecycle boundaries with
fixtures. They never contact a backend or represent a deployed game. Solar2D's
unused `lfs` import has an empty fixture. Unity API compilation does not execute
Unity-native methods, import a project, validate the editor's assembly importer,
link native code or build a player. Host-engine/game smoke verification remains
necessary before production use.

Negative controls corrupt temporary copies, not checked-in source: a C# error,
an editor-only API in a player assembly, a TypeScript type error, a Lua syntax
error, a missing Unity assembly and a wrong
package inventory must each fail. These expected failures belong to the passing
test suite; real-package failures are never suppressed or retried.

Packages and a SHA-256 receipt are generated under `.sdk-build/`. This is local
validation: no registry publication, tag creation, package-version change or
replacement of an existing release. The settings namespace and existing asset
GUIDs, endpoints, tokens, migration, storage and public API contracts stay intact.

## Reference provenance

Primary sources read on 2026-11-02 (14:19–14:25 and 16:14–16:20 UTC):

- [Unity 2022.3 managed plug-ins](https://docs.unity3d.com/2022.3/Documentation/Manual/UsingDLL.html)
  documents external compilation against Unity assemblies. The
  [official release API](https://services.api.unity.com/unity/editor/release/v1/releases?version=2022.3.0f1)
  identifies the original Linux archive. Its published MD5 was verified before
  recording the SHA-256 pin.
- [Unity package layout](https://docs.unity3d.com/2022.3/Documentation/Manual/cus-layout.html)
  documents scripts and assembly definitions. The runtime definition supplies
  the assembly already referenced by this package's editor definition.
- [Creator 2.4 TypeScript](https://docs.cocos.com/creator/2.4/manual/en/scripting/typescript.html)
  describes generated `creator.d.ts`. The
  [official benchmark project](https://github.com/cocos/cocos-benchmark-legacy/tree/6670fdc873e994b0a7449d836374a87d15d545f3)
  provides unmodified declarations and identifies Creator in `project.json`.
- [Solar2D's Lua introduction](https://docs.coronalabs.com/guide/start/introLua/index.html)
  identifies Lua 5.1; the [Lua manual](https://www.lua.org/manual/5.1/)
  describes `luac -p`. JSON comes from Solar2D's
  [original source revision](https://github.com/coronalabs/corona/tree/22368dfc12090d3f61235050c7ff62a28ad6073e/platform/resources).

Keep references genuine: packages that publicize or strip Unity assemblies can
hide inaccessible-API errors and cannot replace original references. A host
fixture or API stub must not be described as an engine or player build.
