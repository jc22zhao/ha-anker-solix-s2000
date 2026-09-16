# Anker Solix — SOLIX S2000 (AS220) fork

A fork of **[thomluther/ha-anker-solix](https://github.com/thomluther/ha-anker-solix)** that adds
support for the **SOLIX S2000 portable power station (model AS220)**.

## Credit

**Nearly all of the work here is [Thomas Luther's](https://github.com/thomluther).**

He built the integration: the Anker cloud and MQTT client, the message-map schema and hex decoders,
the `DeviceHexDataTypes` vocabulary, the command templates, the coordinator, the config flow, and
the entity layer that turns any of it into Home Assistant entities. He also wrote the
[anker-solix-api](https://github.com/thomluther/anker-solix-api) library this vendors, and he
documented the protocol well enough that adding a new device meant filling in field offsets rather
than reverse-engineering a format.

This fork contributes one file of AS220 field offsets, decoded against a live unit, in the format
he defined. That is the whole of it.

If this integration is useful to you, the person to thank — and to
[sponsor](https://github.com/sponsors/thomluther) — is him. **Please do not raise issues with him
about anything in this fork.** Use [this repo's issue
tracker](https://github.com/jc22zhao/ha-anker-solix-s2000/issues), or better, use upstream if you
can reproduce the problem there.

**For full documentation — installation, configuration, supported devices, entity reference — see
the [upstream README](https://github.com/thomluther/ha-anker-solix/blob/main/README.md).** It is
deliberately not duplicated here, because a copy would go stale. Everything in it applies to this
fork unchanged.

## Scope and warranty

**This fork exists for one device: my own S2000.** It is tested on exactly one unit — firmware
1.0.2.2, CA region. It is not tested on any other S2000, any other firmware, any other region, or
any other Anker device.

**There is no guarantee it works for you, on the S2000 or anything else.** Support for every other
device comes from upstream and is untouched here, but this fork tracks a specific upstream tag
rather than upstream's latest release, so you will be behind on fixes for those devices. If you do
not have an S2000, you want upstream, not this.

It writes to the device. Use it at your own risk.

## What this fork adds

The AS220 device support lives in a single file —
[`custom_components/anker_solix/local_as220.py`](custom_components/anker_solix/local_as220.py) —
plus a two-line hook in `__init__.py`. Nothing inside the vendored `solixapi/` tree is modified,
which is deliberate: upstream replaces that directory wholesale on each sync with the API library,
so anything placed inside it would conflict on every release. Registering into `SOLIXMQTTMAP` at
runtime instead keeps the device support itself free of modified upstream files.

Item 3 is the exception and the only one: it is a behavioural fix, not device support, and it edits
`coordinator.py` and `__init__.py` directly. Expect a merge conflict in both on each upstream sync.
The change is small and self-contained, and resolving that conflict by hand is preferable to losing
it — without it, any Anker rate-limit stalls the integration until a human clicks Reconfigure.

1. **AS220 telemetry** — the `0421` / `0900` message map (~13 field groups: SoC, main battery SoC,
   AC input/output power, DC input, USB power, temperature, remaining runtime, usage mode, SoH, AC
   frequency, charge limits), plus `0057`, `0100`, `0402`, `0504` and `0830`. Registered only if
   upstream has not already supplied its own AS220 map.

2. **`0103` SoC-limit control with the app's 80 % floor removed.** This is the reason the fork
   exists. The Anker app's charge-limit slider bottoms out at 80 %, but that is a UI clamp only —
   the device accepts and holds values below it. Confirmed on two units: writing 70 held across
   three telemetry polls, and the app itself then *displayed* 70 % while still refusing to set it.
   Upstream [declined this](https://github.com/thomluther/anker-solix-api/issues/322) on policy —
   *"I do not plan to support options that are not supported by the App, even if they might work"* —
   which is an entirely reasonable line for a shared integration to hold. It is kept here because
   time-of-use arbitrage on Ontario's ULO tariff needs a charge ceiling well under 80 %.

   `max_soc` is offered at 30–100, `min_soc` at 1–90. The shared `CMD_SOC_LIMITS_V2` template that
   A1761/A1763/A1765 reference is rebuilt with `|` rather than mutated, so those devices keep the
   app's limits.

   > **Caution:** `0103` carries `aa` (max) and `ab` (min) in a single frame, so writing one also
   > rewrites the other from the integration's cache — observed silently reverting `min_soc` 10 → 5.
   > Set min first, then max.

   > **Caution:** holding a pack well below full indefinitely can let the SoC gauge drift, since
   > packs typically re-reference near full charge. Letting it reach 100 % occasionally is prudent.

3. **Anker rate limiting no longer demands a manual reconfigure.** Upstream catches
   `AnkerSolixApiClientRetryExceededError` in the same `except` clause as
   `AnkerSolixApiClientAuthenticationError` and raises `ConfigEntryAuthFailed` for both. That is a
   terminal state in Home Assistant: the config entry is unloaded, every device-detail entity built
   in `async_setup_entry` is destroyed, and a reauth card waits for a human — even though the
   stored credentials are fine and Anker's throttle (api error `100053`) clears on its own. Hitting
   Reconfigure and retyping the same username and password therefore "fixes" it only by virtue of
   time having passed. The conflation is visible in the source: the docstring on
   `AnkerSolixApiClientRetryExceededError` reads *"Exception to indicate an authentication error"*,
   copy-pasted from the class above it.

   Here the two are split. `RetryExceeded` raises `UpdateFailed(retry_after=900)` in the coordinator
   and `ConfigEntryNotReady` during setup — both of which Home Assistant retries with its own
   backoff. A genuinely wrong password still raises `ConfigEntryAuthFailed` and still surfaces the
   reauth card, which is the behaviour that clause was written for.

   Not device-specific, and worth upstreaming.

`register()` is written to shrink as upstream catches up: once a release ships its own AS220 map,
that map wins and only the still-missing pieces are filled in. When nothing is left to add, the file
can be deleted and the fork retired.

## Upstream status

AS220 support is in progress upstream — see
[ha-anker-solix#578](https://github.com/thomluther/ha-anker-solix/issues/578),
[anker-solix-api#322](https://github.com/thomluther/anker-solix-api/issues/322) and
[#326](https://github.com/thomluther/anker-solix-api/issues/326). A beta with AS220 telemetry is
expected. **If you have an S2000, wait for it** unless you specifically need a sub-80 % charge
ceiling.

## Installation

HACS → three-dot menu → **Custom repositories** → add
`https://github.com/jc22zhao/ha-anker-solix-s2000` as an **Integration**. Remove the upstream
`Anker Solix` repository from HACS first — both install to `custom_components/anker_solix/` and
cannot coexist.

The domain stays `anker_solix`, so an existing config entry, entity IDs and recorder history all
carry over untouched. `solixapi/authcache` is declared as a HACS `persistent_directory`, so the auth
cache survives too.

This repo publishes **no GitHub releases**, so HACS tracks the default branch.

## Keeping current with upstream

```sh
git remote add upstream https://github.com/thomluther/ha-anker-solix.git
git fetch upstream --tags
git merge 3.7.1          # or whichever tag you want
```

Currently based on upstream **3.7.0**. The only files this fork touches are `local_as220.py` (new),
`__init__.py` (two lines), `README.md`, `INFO.md`, `hacs.json` and `manifest.json`, so merges should
be conflict-free apart from the metadata files.

## Licence

MIT, unchanged from upstream. Copyright (c) 2024 Thomas Luther. See [LICENSE](LICENSE).
