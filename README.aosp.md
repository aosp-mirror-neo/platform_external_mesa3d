# AOSP Mesa Upstream-Only Development and Maintenance Policy

`external/mesa3d` is the canonical Mesa3D integration for Android. Historically, Mesa3D in Android
has been haphazardly maintained and informally staffed, leading to long periods of stagnation
(documented in the [public roadmap][mesa-public-roadmap]).

We have found that an _upstream-only_ development model
[best serves both internal and external customers](#appendix-i-upstream-first-approach-increases-aosp-mesa-updates).
This document outlines key aspects of this model.

______________________________________________________________________

## 1. Overall Goals

`external/mesa3d` targets open-source Vulkan drivers that are useful internally to teams inside
Google.

### 1.1 Supported Drivers

| Driver                                      | Long-term use case                              | In-tree users                                          |
| :------------------------------------------ | :---------------------------------------------- | :----------------------------------------------------- |
| **gfxstream** (`vulkan.ranchu`)             | Cloud testing and emulators                     | `device/google/cuttlefish`, `device/google/goldfish`   |
| **Lavapipe** (`vulkan.lvp`)                 | [Early device bring-up][lavapipe-early-bringup] | `device/google/cuttlefish`, and Pixel images projected |
| **Turnip / Freedreno** (`vulkan.freedreno`) | DragonBoards, others experimenting              | None yet, but `device/linaro/dragonboard` projected    |

### 1.2 Future Targeted Drivers

Key future driver targets for AOSP Mesa include:

- **ARM**: [PanVK and Panfrost][arm-tyr-rust-driver] (Mali / Immortalis GPUs)
- **Imagination**: [PowerVR open-source drivers][imagination-open-source]

______________________________________________________________________

## 2. Design

AOSP Mesa is structured to avoid long-term maintenance failure modes (detailed in
[Appendix II, A](#a-heavyweight-antipatterns-we-should-avoid)) by standardizing on a single,
canonical upstream-tracking repository driven by automated build generation and shared maintenance.

### 2.1 OWNERS

`external/mesa3d` is targeted for use by multiple Android teams and is best served by a formal
rotation structure among them.

- **AOSP Mesa Rotation (primary)**: The primary point of contact is the
  [AOSP Mesa rotation][aosp-mesa-rotation]. Ideally, the rotation would have 1–3 active engineers,
  depending on the number of downstream consumers.

  - *Rotation Qualification Criteria*:
    1. Agree to adhere strictly to the rules outlined in Section 3.
    1. Commit ~2 SWE weeks per year toward tooling maintenance, automation (meson2hermetic,
       Copybara/Skia), and dependency management.

- **Past Mesa-in-Google Maintainers (secondary)**: As a backup if the rotation becomes defunct, past
  Mesa-in-Google maintainers serve as escalation contacts.

### 2.2 Current Update Strategy: meson2hermetic

Integrating Mesa3D with the Soong build system is a major challenge. Each new graphics driver adds
2–3 kLoC of build code. Without automation, updates would become unmanageable.

`external/mesa3d` relies on [meson2hermetic][meson2hermetic-pr] to automatically generate
`Android.bp` build files. There are multiple advantages to using meson2hermetic:

1. **Official Meson Integration**: It aims to be officially integrated into the Meson build system,
   enabling a shared, open-source understanding of how to properly integrate Mesa3D into Android
   long-term.
1. **Direct Conversion (No Intermediate Build System)**: Other converters often convert to an
   intermediate representation (Ninja) before trying to reconstruct the rules, which leads to a loss
   of precision.

Due to a small number of reviewers, meson2hermetic is not yet upstream.

### 2.4 Current workflow

- - *Merge upstream*
  ```sh
    cd main/external/mesa3d
    git fetch goog
    git merge goog/upstream-main
  ```

For a shallow clone of `external/mesa3d`, the merge step may take ~30 minutes as git re-builds the
commit history. Do something else while that happens in another terminal. Subsequent merges will be
faster.

Power users may just create a Mesa3D checkout outside of the full Android tree to enable merging.

```sh
    glogin
    git clone --origin goog sso://googleplex-android/platform/external/mesa3d external_mesa3d
```

Enable change IDs:

```sh
   cd external_mesa3d
   curl -Lo .git/hooks/commit-msg https://gerrit-review.googlesource.com/tools/hooks/commit-msg && chmod +x .git/hooks/commit-msg
```

This would avoid churn for those who often re-create full Android trees.

- *Transpilation commit*:

  ```sh
  cd main/external/mesa3d
  ./meson2hermetic.sh
  ```

- *Push commits*:

```sh
    git push goog HEAD:refs/for/main
```

Currently, we are updating Mesa every 2 weeks.

### 2.5 Future Goal: Full Update Automation

In the future, ideally upstream Mesa will be continuously tracked and synchronized into
`external/mesa3d` using automated rolling pipelines (such as the
[Skia autoroller][skia-autoroller-mesa-android] or Copybara).

```
+---------------+ Copybara OR Skia Autoroller  +-------------------+
| Upstream Mesa | ---------------------------> |  external/mesa3d  |
+---------------+        meson2hermetic        +-------------------+
                                                       ^
                                                       |
                                                       | (Super-rare "ANDROID:" patches)
                                               +-------------------+
                                               | AOSP Mesa Rotation|
                                               +-------------------+
```

______________________________________________________________________

## 3. Rules

The following rules enforce the _upstream-only_ approach in `external/mesa3d`. The key principle
behind these rules is that updating Mesa3D should be straightforward, and only becomes difficult
when diverging from upstream. Therefore, downstream divergence is strictly prohibited.

For teams requiring specialized release milestone stabilization, temporary alternatives are outlined
in [Appendix II, B](#b-temporary-antipatterns-branchesprebuilts-that-are-more-easily-maintainable).

1. **Submit Patches to Upstream Mesa First**:

   - Downstream patches to upstream files are not permitted in AOSP. All patches must be merged
     upstream before being integrated into Android.
   - Pre-merge testing on Android CI is encouraged before upstream submission using `ATBD+1` and
     `Presubmit+1`.
   - Temporary test defines and experimental flags (e.g., `-DGFXSTREAM_TESTING_WEIRD_ANDROID_QUIRK`
     or driver quirks) must be merged upstream and subsequently reverted upstream; they may not be
     introduced as downstream-only patches.
   - Downstream patches are strictly limited to Android-specific repository metadata (e.g.,
     `README.aosp.md`, `METADATA`).

1. **Standardized Two-Commit Upstream Update Structure**:

   - Every update from upstream must consist of exactly two commits:
     1. **Merge Commit**: A single git merge commit pulling the upstream Mesa revision (see
        [example 1][update-example-merge-cl]).
     1. **Build Generation Commit**: A commit regenerating the Soong build configuration
        (`Android.bp`) using the upstream version of `meson2hermetic` (see
        [example 2][update-example-soong-gen-cl]).
   - Direct manual editing of `Android.bp` files is strictly prohibited.
   - If `meson2hermetic` generates an incorrect build file:
     - Submit an MR to [magma-gpu/meson][mesonbuild-repo] if the defect is in `meson2hermetic`.
     - Submit an MR to [upstream Mesa][upstream-mesa-repo] if the defect is in Mesa's `meson.build`
       files.

1. **Handling Breakages and Regressions**:

   - If an upstream update introduces a breaking change not caught by Android CI:
     - Revert the AOSP update commits; OR
     - Revert the offending commit in upstream Mesa and perform a subsequent sync.
   - Downstream workarounds or temporary patches in AOSP are strictly forbidden.

1. **CI Testing and Test Quarantine Policy**:

   - Critical product tests should run in Android CI presubmits to prevent post-merge regressions.
   - Adding a new graphics driver (e.g., Imagination) to the build configuration requires approval
     from the AOSP Mesa rotation.
   - If an existing test fails and blocks updates, the team owning the test must resolve the issue
     in upstream Mesa within a reasonable timeframe (2–3 weeks). Tests exceeding this window will be
     quarantined or disabled to prevent blocking others.

______________________________________________________________________

# Appendix I: Upstream-first approach increases AOSP Mesa updates

| Era                               | Timeframe       | Upstream Merges | Avg. Cadence       | Primary Characteristics                                                                          |
| :-------------------------------- | :-------------- | :-------------: | :----------------- | :----------------------------------------------------------------------------------------------- |
| **Initial Import & Stagnation**   | 2011 – 2016     |      **1**      | ~1 sync / 5 years  | Initial import in Jan 2011; single sync in 2013 (Mesa 9.0.3). Long freeze period.                |
| **Periodic Release Syncs**        | 2017 – 2021     |      **6**      | ~1 sync / year     | Point-in-time updates to stable branches (17.0, 18.0, 19.1, 20.0, 20.3.4). High rebase friction. |
| **Hiatus / Stagnation**           | 2022 – 2023     |      **0**      | 0 syncs            | 3-year gap without upstream merges; divergence of internal modifications.                        |
| **Modern Upstream-First Cadence** | 2024 – 2026 YTD |     **20**      | ~1–2 syncs / month | Continuous rolling against `upstream-main`, automated transpilation via `meson2hermetic`.        |
| **Total (All-Time)**              | **2011 – 2026** |     **28**      | —                  | **71% of all historical upstream merges occurred in 2024–2026.**                                 |

______________________________________________________________________

# Appendix II: Common Antipatterns

### (A) Heavyweight antipatterns we should avoid

- **Runaway Fragmentation (Forks in `/vendor/`)**: Allowing unconstrained downstream forks in
  `/vendor/` (e.g., `/vendor/google/graphics/{subteam}/mesa3d/{version}`) results in substantial
  technical debt and duplicate dependencies. This pattern is visible in historical ARM Mali driver
  distributions where over eight separate versions of Mali and embedded LLVM runtimes coexisted
  (`vendor/arm/mali/*`), as well as separate downstream Mesa repositories
  (`vendor/google/graphics/desktop/mesa3d/intel`, `panvk`).
- **Monolithic Stagnation (Downstream Patch Accumulation)**: Maintaining a single repository that
  diverges with downstream patches creates heavy rebase burdens and instability. In Google3, a
  single Mesa version accumulated fragmented downstream patches from multiple teams, resulting in
  difficult syncs and repeated reverts (e.g., [CL 893178482][google3-cl-893178482]).

### (B) Temporary antipatterns (branches/prebuilts) that are more easily maintainable

For teams requiring temporary divergence, release milestone freezes, or extended qualification
cycles:

- **Prebuilts and Milestone Branches**: Teams requiring fixed release milestones can utilize
  prebuilts built from `main` or maintain dedicated branches in `external/mesa3d` (e.g.,
  [magma branch request][mesa-magma-branch-bug]). This pattern has been successfully validated by
  SDV Media (see [SDV Media Migration Plan][sdv-media-migration-plan-doc],
  [SDV Media Mesa Prebuilts][sdv-media-prebuilts-topic]).
- **Tiered Repository Architecture**:
  - `external/mesa3d`: Canonical upstream-first bleeding-edge tree.
  - Dedicated branches and prebuilts for specialized platform configurations.

[aosp-mesa-rotation]: https://rotations.corp.google.com/rotation/5577216602144768
[arm-tyr-rust-driver]: https://www.collabora.com/news-and-blog/news-and-events/introducing-tyr-a-new-rust-drm-driver.html
[google3-cl-893178482]: https://critique.corp.google.com/cl/893178482
[imagination-open-source]: https://blog.imaginationtech.com/imagination-and-our-commitment-to-open-source
[lavapipe-early-bringup]: https://buganizer.corp.google.com/issues/441971955
[mesa-magma-branch-bug]: https://buganizer.corp.google.com/issues/385197313
[mesa-public-roadmap]: https://gitlab.freedesktop.org/mesa/mesa/-/issues/13776
[meson2hermetic-pr]: https://github.com/mesonbuild/meson/pull/15462
[mesonbuild-repo]: https://github.com/magma-gpu/mesonbuild
[sdv-media-migration-plan-doc]: https://docs.google.com/document/d/1R2khIgJoGABF5cYMgjCAtu0rLDX238fN4ydvYtUVWws/edit?tab=t.0
[sdv-media-prebuilts-topic]: https://googleplex-android-review.git.corp.google.com/q/topic:%22sdv-mesa-prebuilts%22
[skia-autoroller-mesa-android]: https://autoroll.skia.org/r/mesa-android
[update-example-merge-cl]: https://googleplex-android-review.git.corp.google.com/c/platform/external/mesa3d/+/39499341
[update-example-soong-gen-cl]: https://googleplex-android-review.git.corp.google.com/c/platform/external/mesa3d/+/39499342
[upstream-mesa-repo]: https://gitlab.freedesktop.org/mesa/mesa
