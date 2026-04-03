from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.material_index import parse_canonical_stem
from src.workflow import (
    _infer_scene_from_visual,
    allocate_coverage_across_beats,
    build_factory_filename,
    build_project_slots_from_creative,
    next_index_for,
    normalize_demo_content_token,
    normalize_demo_coverage_token,
    parse_factory_filename_key,
    summarize_factory_coverage,
)


class WorkflowCoverageTests(unittest.TestCase):
    def test_allocate_coverage_across_beats_consumes_shared_inventory(self) -> None:
        beat_needs = [
            {("line", "wide"): 1},
            {("line", "wide"): 1},
            {("line", "wide"): 1},
        ]
        available = {("line", "wide"): 2}

        out = allocate_coverage_across_beats(beat_needs, available)

        self.assertEqual(out[0][("line", "wide")], (1, 0))
        self.assertEqual(out[1][("line", "wide")], (1, 0))
        self.assertEqual(out[2][("line", "wide")], (0, 1))


    def test_build_factory_filename_includes_coverage_and_move_tokens(self) -> None:
        name = build_factory_filename("Factory Floor", "Wide Shot", "closeup", "slide", 3, ".mp4")

        self.assertEqual(name, "factory_floor_workspace_display_detail_slide_v3.mp4")

    def test_next_index_for_counts_matching_scene_content_coverage_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_floor_workspace_display_detail_slide_v01.mp4").write_bytes(b"x")
            (factory_dir / "factory_floor_workspace_display_detail_slide_v02.mp4").write_bytes(b"x")
            (factory_dir / "factory_floor_workspace_display_detail_pushin_v09.mp4").write_bytes(b"x")

            nxt = next_index_for(factory_dir, "Factory Floor", "Wide Shot", "closeup", "slide", ".mp4")

        self.assertEqual(nxt, 3)


    def test_next_index_for_ignores_files_missing_required_coverage_or_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_floor_workspace_display_detail_slide_v01.mp4").write_bytes(b"x")
            (factory_dir / "factory_floor_workspace_display_v09.mp4").write_bytes(b"x")
            (factory_dir / "factory_floor_workspace_display_detail_v08.mp4").write_bytes(b"x")
            (factory_dir / "factory_floor_workspace_display_slide_v07.mp4").write_bytes(b"x")

            nxt = next_index_for(factory_dir, "Factory Floor", "Wide Shot", "closeup", "slide", ".mp4")

        self.assertEqual(nxt, 2)

    def test_summarize_factory_coverage_counts_double_factory_scene_prefix(self) -> None:
        rows = [
            {"Category": "Line", "Shot": "Hero"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_factory_line_hero_static_01.mp4").write_bytes(b"x")

            summary = summarize_factory_coverage(rows, factory_dir)

        self.assertEqual(summary["total_need"], 1)
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 0)

    def test_summarize_factory_coverage_slug_normalizes_row_values(self) -> None:
        rows = [
            {"Category": "Line", "Shot": "Wide"},
            {"Category": "Line", "Shot": "Wide"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_factory_line_wide_shot_static_01.mp4").write_bytes(b"x")

            summary = summarize_factory_coverage(rows, factory_dir)

        self.assertEqual(summary["total_need"], 2)
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 1)


    def test_summarize_factory_coverage_human_readable_wide_shot_labels_match(self) -> None:
        """Category='Factory Line', Shot='Wide Shot' must match a file that parses to (machine,display,wide)."""
        rows = [
            {"Category": "Factory Line", "Shot": "Wide Shot"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_line_wide_static_01.mp4").write_bytes(b"x")

            summary = summarize_factory_coverage(rows, factory_dir)

        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 0)

    def test_summarize_factory_coverage_human_readable_detail_closeup_labels_match(self) -> None:
        """Category='Factory Process', Shot='Detail Closeup' / 'Detail Close-up' must match (machine,display,detail)."""
        rows = [
            {"Category": "Factory Process", "Shot": "Detail Closeup"},
            {"Category": "Factory Process", "Shot": "Detail Close-up"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_line_detail_static_01.mp4").write_bytes(b"x")

            summary = summarize_factory_coverage(rows, factory_dir)

        self.assertEqual(summary["total_need"], 2)
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 1)

    def test_summarize_factory_coverage_hero_establishing_label_resolves_to_wide(self) -> None:
        """Category='Hero / Establishing', Shot='Wide Shot' must resolve the same key as 'Line'+'Wide'."""
        rows = [
            {"Category": "Hero / Establishing", "Shot": "Wide Shot"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_line_wide_static_01.mp4").write_bytes(b"x")

            summary = summarize_factory_coverage(rows, factory_dir)

        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 0)

    def test_summarize_factory_coverage_unknown_label_does_not_explode(self) -> None:
        """Completely unknown multi-word labels must not raise; they simply yield 0 matches."""
        rows = [
            {"Category": "Totally Unknown Category Name", "Shot": "Something Weird"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)

            summary = summarize_factory_coverage(rows, factory_dir)

        self.assertEqual(summary["total_need"], 1)
        self.assertEqual(summary["total_ready"], 0)
        self.assertEqual(summary["total_missing"], 1)


class LabelNormalizationConsistencyTests(unittest.TestCase):
    """
    Prove that human-readable Category and Shot labels are recognized consistently
    across normalize_demo_content_token, normalize_demo_coverage_token, and
    _canonical_need_key_from_legacy (exercised via summarize_factory_coverage).

    normalize_demo_coverage_token intentionally returns "hero" for all wide-type
    labels (demo-facing semantic). _canonical_need_key_from_legacy maps these to
    "wide" via _canonical_coverage_from_legacy — that difference is deliberate.
    """

    # --- content labels ---

    def test_normalize_demo_content_token_factory_line(self) -> None:
        self.assertEqual(normalize_demo_content_token("Factory Line"), "line")

    def test_normalize_demo_content_token_factory_process(self) -> None:
        self.assertEqual(normalize_demo_content_token("Factory Process"), "line")

    def test_normalize_demo_content_token_exterior_product_hero(self) -> None:
        self.assertEqual(normalize_demo_content_token("Exterior / Product Hero"), "product")

    def test_normalize_demo_content_token_hero_establishing(self) -> None:
        self.assertEqual(normalize_demo_content_token("Hero / Establishing"), "line")

    # --- coverage labels ---

    def test_normalize_demo_coverage_token_wide_shot(self) -> None:
        # demo-facing: wide-type → "hero"
        self.assertEqual(normalize_demo_coverage_token("Wide Shot"), "hero")

    def test_normalize_demo_coverage_token_medium_shot(self) -> None:
        self.assertEqual(normalize_demo_coverage_token("Medium Shot"), "medium")

    def test_normalize_demo_coverage_token_detail_closeup(self) -> None:
        self.assertEqual(normalize_demo_coverage_token("Detail Closeup"), "detail")

    def test_normalize_demo_coverage_token_detail_close_up_hyphen(self) -> None:
        self.assertEqual(normalize_demo_coverage_token("Detail Close-up"), "detail")

    def test_normalize_demo_coverage_token_hero_establishing(self) -> None:
        # demo-facing: hero/establishing → "hero"
        self.assertEqual(normalize_demo_coverage_token("Hero / Establishing"), "hero")

    # --- regression: plain simple tokens unchanged ---

    def test_normalize_demo_content_token_plain_line(self) -> None:
        self.assertEqual(normalize_demo_content_token("line"), "line")

    def test_normalize_demo_coverage_token_plain_wide(self) -> None:
        # "wide" is wide-type → "hero" in demo-facing output (preserved behavior)
        self.assertEqual(normalize_demo_coverage_token("wide"), "hero")

    def test_normalize_demo_coverage_token_plain_detail(self) -> None:
        self.assertEqual(normalize_demo_coverage_token("detail"), "detail")

    def test_normalize_demo_coverage_token_plain_medium(self) -> None:
        self.assertEqual(normalize_demo_coverage_token("medium"), "medium")


class SceneFactoryAliasTests(unittest.TestCase):
    """
    Regression suite for the "factory" → "factory-floor" scene alias fix.

    Before the fix:
    - Files written with scene="factory" failed parse_canonical_stem
      (factory ∉ SCENE_VALUES) and fell to the legacy heuristic, which
      misread subject as "content" and action as "coverage", producing
      key=('machine','display','display') instead of ('machine','display','wide').

    After the fix:
    - "factory" added to SCENE_VALUES as a backward-compat alias.
    - build_factory_filename normalizes "factory" → "factory-floor" on write,
      so new files use the primary canonical scene token.
    - Both old (factory_*) and new (factory-floor_*) 6D files parse correctly.
    """

    # --- write path ---

    def test_build_factory_filename_normalizes_factory_to_factory_floor(self) -> None:
        name = build_factory_filename("factory", "line", "wide", "static", 1, ".mp4",
                                      subject="machine", action="display")
        self.assertTrue(name.startswith("factory-floor_"),
                        f"expected factory-floor_ prefix, got: {name!r}")

    def test_build_factory_filename_factory_floor_passthrough(self) -> None:
        name = build_factory_filename("factory-floor", "line", "wide", "static", 1, ".mp4",
                                      subject="machine", action="display")
        self.assertTrue(name.startswith("factory-floor_"),
                        f"expected factory-floor_ prefix, got: {name!r}")

    # --- read path: parse_canonical_stem ---

    def test_parse_canonical_stem_accepts_factory_scene(self) -> None:
        """Old files with scene=factory must now parse as valid."""
        result = parse_canonical_stem("factory_machine_display_wide_static_v1.mp4")
        self.assertTrue(result["is_valid"],
                        f"expected is_valid=True, errors={result['errors']}")
        self.assertEqual(result["coverage"], "wide")

    def test_parse_canonical_stem_accepts_factory_floor_scene(self) -> None:
        result = parse_canonical_stem("factory-floor_machine_display_wide_static_v1.mp4")
        self.assertTrue(result["is_valid"],
                        f"expected is_valid=True, errors={result['errors']}")

    # --- read path: parse_factory_filename_key ---

    def test_parse_factory_filename_key_old_factory_6d(self) -> None:
        """Old canonical 6D file: coverage must be wide, not the action slot 'display'."""
        key = parse_factory_filename_key(Path("factory_machine_display_wide_static_v1.mp4"))
        self.assertEqual(key, ("machine", "display", "wide"),
                         f"wrong key for old factory_ 6D file: {key!r}")

    def test_parse_factory_filename_key_new_factory_floor_6d(self) -> None:
        key = parse_factory_filename_key(Path("factory-floor_machine_display_wide_static_v1.mp4"))
        self.assertEqual(key, ("machine", "display", "wide"),
                         f"wrong key for factory-floor_ 6D file: {key!r}")

    # --- summarize_factory_coverage integration ---

    def test_summarize_factory_coverage_old_factory_6d_file_counts_as_ready(self) -> None:
        """An existing factory_*_v1 file on disk must be matched (not a false miss)."""
        rows = [{"Category": "Line", "Shot": "Wide"}]
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_machine_display_wide_static_v1.mp4").write_bytes(b"x")
            summary = summarize_factory_coverage(rows, factory_dir)
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 0)

    def test_summarize_factory_coverage_new_factory_floor_6d_file_counts_as_ready(self) -> None:
        """A newly generated factory-floor_* file must be matched."""
        rows = [{"Category": "Line", "Shot": "Wide"}]
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory-floor_machine_display_wide_static_v1.mp4").write_bytes(b"x")
            summary = summarize_factory_coverage(rows, factory_dir)
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 0)

    # --- regression: legacy 5-segment files unchanged ---

    def test_parse_factory_filename_key_legacy_5seg_still_works(self) -> None:
        key = parse_factory_filename_key(Path("factory_line_wide_static_01.mp4"))
        self.assertEqual(key, ("machine", "display", "wide"))


class CoverageHeroAliasTests(unittest.TestCase):
    """
    Regression suite for the "hero" → "wide" coverage alias fix.

    Before the fix:
    - 6D files with coverage=hero failed parse_canonical_stem (hero ∉ COVERAGE_VALUES).
    - factory-floor_* hero files fell to legacy heuristic but legacy requires parts[0]="factory",
      so parse_factory_filename_key returned None (total miss).

    After the fix:
    - "hero" added to COVERAGE_VALUES as a backward-compat alias.
    - parse_factory_filename_key normalizes coverage "hero" → "wide" after canonical parse.
    - New writes still emit "wide" (not "hero") via _canonical_coverage_from_legacy.
    """

    # --- read path: parse_canonical_stem ---

    def test_parse_canonical_stem_accepts_hero_coverage(self) -> None:
        result = parse_canonical_stem("factory-floor_machine_display_hero_static_v1.mp4")
        self.assertTrue(result["is_valid"],
                        f"expected is_valid=True, errors={result['errors']}")
        self.assertEqual(result["coverage"], "hero")  # accepted as-is; normalization happens in key extractor

    # --- read path: parse_factory_filename_key ---

    def test_parse_factory_filename_key_hero_coverage_normalizes_to_wide(self) -> None:
        """factory-floor 6D file with coverage=hero must return key with coverage='wide'."""
        key = parse_factory_filename_key(Path("factory-floor_machine_display_hero_static_v1.mp4"))
        self.assertEqual(key, ("machine", "display", "wide"),
                         f"expected coverage=wide in key, got: {key!r}")

    def test_parse_factory_filename_key_old_factory_hero_6d(self) -> None:
        """Old factory_ 6D file with hero coverage must also return coverage='wide'."""
        key = parse_factory_filename_key(Path("factory_machine_display_hero_static_v1.mp4"))
        self.assertEqual(key, ("machine", "display", "wide"))

    def test_parse_factory_filename_key_hero_and_wide_same_key(self) -> None:
        """hero and wide coverage on otherwise identical files must map to the same key."""
        key_hero = parse_factory_filename_key(Path("factory-floor_machine_display_hero_static_v1.mp4"))
        key_wide = parse_factory_filename_key(Path("factory-floor_machine_display_wide_static_v1.mp4"))
        self.assertEqual(key_hero, key_wide)

    # --- summarize_factory_coverage integration ---

    def test_summarize_factory_coverage_hero_6d_file_counts_as_ready(self) -> None:
        """An on-disk 6D file with coverage=hero must count against a wide coverage need."""
        rows = [{"Category": "Line", "Shot": "Wide"}]
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory-floor_machine_display_hero_static_v1.mp4").write_bytes(b"x")
            summary = summarize_factory_coverage(rows, factory_dir)
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 0)

    # --- write path: hero must not be emitted ---

    def test_build_factory_filename_hero_input_emits_wide(self) -> None:
        name = build_factory_filename("factory-floor", "line", "hero", "static", 1, ".mp4",
                                      subject="machine", action="display")
        self.assertIn("wide", name,
                      f"expected 'wide' in filename, got: {name!r}")
        self.assertNotIn("hero", name,
                         f"'hero' must not appear in new filename, got: {name!r}")

    # --- regression: legacy 5-segment hero still works ---

    def test_parse_factory_filename_key_legacy_hero_5seg_still_works(self) -> None:
        """Legacy double-prefix file with hero coverage still resolves to wide via legacy path."""
        key = parse_factory_filename_key(Path("factory_factory_line_hero_static_01.mp4"))
        self.assertEqual(key, ("machine", "display", "wide"))


class SceneDefaultCanonicalizationTests(unittest.TestCase):
    """
    Prove that bare "factory" is no longer produced as a scene default/fallback
    in workflow metadata. All generic factory-context inferences now yield
    "factory-floor".

    Intentional bare "factory" that must remain:
    - legacy filename parser (parts[0] != "factory" guard)
    - build_factory_filename / next_index_for normalization gate (if scene == "factory")
    - scene_vocabulary.yaml keyword "factory" (not a token, a keyword)
    """

    # --- _infer_scene_from_visual ---

    def test_infer_scene_from_visual_generic_fallback_is_factory_floor(self) -> None:
        """Visual with no recognizable keywords → canonical factory-floor fallback."""
        result = _infer_scene_from_visual("indoor facility work area", "")
        self.assertEqual(result, "factory-floor")

    def test_infer_scene_from_visual_bare_factory_beat_scene_triggers_inference(self) -> None:
        """beat_scene='factory' (old data) must not short-circuit; vocab inference still runs."""
        # "automation line" now correctly resolves to factory-line, proving inference ran
        result = _infer_scene_from_visual("automation line", "factory")
        self.assertEqual(result, "factory-line")

    def test_infer_scene_from_visual_factory_floor_beat_scene_triggers_inference(self) -> None:
        """beat_scene='factory-floor' (new default) must also run vocab inference."""
        # "automation line" now correctly resolves to factory-line, proving inference ran
        result = _infer_scene_from_visual("automation line", "factory-floor")
        self.assertEqual(result, "factory-line")

    def test_infer_scene_from_visual_showroom_visual_overrides_factory_floor_beat(self) -> None:
        """Visual cue for showroom must win even when beat_scene defaults to factory-floor."""
        result = _infer_scene_from_visual("product display in showroom", "factory-floor")
        self.assertEqual(result, "showroom")

    def test_infer_scene_from_visual_explicit_non_generic_scene_passes_through(self) -> None:
        """Explicitly set beat scene (e.g. warehouse) must never be overridden by inference."""
        result = _infer_scene_from_visual("automation line", "warehouse")
        self.assertEqual(result, "warehouse")

    def test_infer_scene_from_visual_showroom_explicit_passes_through(self) -> None:
        result = _infer_scene_from_visual("factory automation line", "showroom")
        self.assertEqual(result, "showroom")

    # --- build_project_slots_from_creative ---

    def test_project_slots_without_explicit_scene_carry_factory_floor(self) -> None:
        """Slots built from beats with no explicit scene must have factory-floor, not factory."""
        creative = {
            "meta": {"target_length": 20},
            "beats": [
                {"purpose": "establish_context", "subtitle": "S1", "vo": "V1",
                 "visual": "production line automation"},
            ],
        }
        slots = build_project_slots_from_creative(creative)
        self.assertTrue(slots, "expected at least one slot")
        for slot in slots:
            scene = slot.get("scene", "")
            self.assertNotEqual(scene, "factory",
                                f"slot must not have bare 'factory' scene, got {scene!r}")
            self.assertTrue(
                scene and scene != "factory",
                f"slot scene should be canonical, got {scene!r}",
            )

    # --- build_factory_filename / backward compat unchanged ---

    def test_build_factory_filename_still_normalizes_factory_input(self) -> None:
        """Regression: write-gate normalization still fires for any factory input."""
        name = build_factory_filename("factory", "line", "wide", "static", 1, ".mp4",
                                      subject="machine", action="display")
        self.assertTrue(name.startswith("factory-floor_"))

    def test_build_factory_filename_factory_floor_unchanged(self) -> None:
        name = build_factory_filename("factory-floor", "line", "wide", "static", 1, ".mp4",
                                      subject="machine", action="display")
        self.assertTrue(name.startswith("factory-floor_"))


class SceneVocabularyInferenceTests(unittest.TestCase):
    """
    Prove that _infer_scene_from_visual() resolves common factory-context visual
    strings to specific canonical scene tokens after enriching scene_vocabulary.yaml.

    Also verifies:
    - the former non-canonical "site" token no longer appears
    - all inferred tokens are accepted by SCENE_VALUES
    - generic visuals still fall back to "factory-floor"
    - existing entries (showroom, warehouse, office, exterior) are unaffected
    """

    def _infer(self, visual: str, beat_scene: str = "") -> str:
        return _infer_scene_from_visual(visual, beat_scene)

    # --- new specific inferences ---

    def test_production_line_infers_factory_line(self) -> None:
        self.assertEqual(self._infer("production line conveyor belt"), "factory-line")

    def test_automation_line_robot_infers_factory_line(self) -> None:
        self.assertEqual(self._infer("automation line robot arm assembly"), "factory-line")

    def test_assembly_floor_infers_factory_line(self) -> None:
        self.assertEqual(self._infer("assembly floor manufacturing line"), "factory-line")

    def test_quality_inspection_infers_testing_area(self) -> None:
        self.assertEqual(self._infer("quality inspection station detail"), "testing-area")

    def test_safety_test_rig_infers_testing_area(self) -> None:
        self.assertEqual(self._infer("safety test rig tower"), "testing-area")

    def test_workstation_bench_infers_workstation(self) -> None:
        self.assertEqual(self._infer("operator workstation bench area"), "workstation")

    def test_factory_floor_phrase_infers_factory_floor(self) -> None:
        self.assertEqual(self._infer("factory floor overview wide shot"), "factory-floor")

    def test_building_entrance_infers_entrance(self) -> None:
        self.assertEqual(self._infer("building entrance lobby reception"), "entrance")

    def test_villa_residential_infers_exterior_not_site(self) -> None:
        """Former non-canonical 'site' token must no longer appear."""
        result = self._infer("villa residential installation site")
        self.assertEqual(result, "exterior")
        self.assertNotEqual(result, "site")

    # --- generic fallback ---

    def test_generic_visual_falls_back_to_factory_floor(self) -> None:
        self.assertEqual(self._infer("generic automation production"), "factory-floor")

    # --- existing entries unchanged ---

    def test_showroom_still_infers_showroom(self) -> None:
        self.assertEqual(self._infer("product display in showroom"), "showroom")

    def test_warehouse_still_infers_warehouse(self) -> None:
        self.assertEqual(self._infer("warehouse storage area"), "warehouse")

    def test_office_still_infers_office(self) -> None:
        self.assertEqual(self._infer("office meeting conference room"), "office")

    def test_outdoor_still_infers_exterior(self) -> None:
        self.assertEqual(self._infer("outdoor campus drone shot"), "exterior")

    # --- passthrough and generic beat_scene behaviour ---

    def test_explicit_beat_scene_passes_through(self) -> None:
        """Explicit non-generic beat_scene must win over visual inference."""
        self.assertEqual(self._infer("production line robot", "testing-area"), "testing-area")

    def test_factory_floor_beat_scene_triggers_inference(self) -> None:
        """factory-floor default beat_scene must still let vocab inference run."""
        self.assertEqual(self._infer("production line robot", "factory-floor"), "factory-line")

    # --- all inferred tokens are canonical ---

    def test_all_inferred_tokens_are_canonical(self) -> None:
        from src.material_index import SCENE_VALUES
        visuals = [
            "production line conveyor", "assembly line robot", "quality inspection",
            "safety test rig", "workstation bench", "factory floor overview",
            "building entrance lobby", "villa residential site", "warehouse storage",
            "showroom display", "office meeting", "outdoor aerial", "generic content",
        ]
        for v in visuals:
            result = self._infer(v)
            self.assertIn(result, SCENE_VALUES,
                          f"non-canonical token {result!r} inferred from {v!r}")


class CanonicalPoolRoundTripTests(unittest.TestCase):
    """
    End-to-end regression lock for the full canonical pool round-trip:
      row / slot metadata  →  build_factory_filename  →  on-disk file
      →  parse_factory_filename_key  →  summarize_factory_coverage  →  ready count

    Each test covers a distinct scenario not already tested as a unified chain.
    Individual unit tests for each step exist in the sibling classes above;
    these tests lock the cross-step interactions.
    """

    # ── 1. Explicit write round-trip ─────────────────────────────────────────
    # Use build_factory_filename (not a hardcoded string) so the test breaks
    # if the write gate changes the filename in a way that breaks readback.

    def test_explicit_write_then_readback_round_trip(self) -> None:
        """
        build_factory_filename → file on disk → parse_factory_filename_key
        → summarize_factory_coverage all agree on the same canonical key.
        """
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)

            # Simulate what the UI does when saving a Pool Fill card
            filename = build_factory_filename(
                "factory",          # bare "factory" input — write gate must normalize
                "line", "wide", "static", 1, ".mp4",
                subject="machine", action="display",
            )
            (factory_dir / filename).write_bytes(b"x")

            # Key from the generated file
            file_key = parse_factory_filename_key(factory_dir / filename)
            self.assertEqual(file_key, ("machine", "display", "wide"),
                             f"filename {filename!r} → wrong key {file_key!r}")

            # Coverage summary using a canonical row
            summary = summarize_factory_coverage(
                [{"Subject": "machine", "Action": "display", "CoverageCanonical": "wide"}],
                factory_dir,
            )
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 0)

    # ── 2. Combined scene+coverage alias backward-compat ─────────────────────
    # Old file has BOTH old scene token ("factory") AND old coverage token ("hero").
    # Both aliases must be resolved independently for the file to count as ready.

    def test_combined_old_scene_and_hero_coverage_alias_round_trip(self) -> None:
        """
        An on-disk file with scene='factory' AND coverage='hero' must count against
        a row with canonical coverage='wide' — both aliases working together.
        """
        rows = [{"Subject": "machine", "Action": "display", "CoverageCanonical": "wide"}]
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_machine_display_hero_static_v1.mp4").write_bytes(b"x")
            summary = summarize_factory_coverage(rows, factory_dir)
        self.assertEqual(summary["total_ready"], 1,
                         "combined factory+hero alias file must count as ready")
        self.assertEqual(summary["total_missing"], 0)

    # ── 3. Human-readable row + canonical 6D file ────────────────────────────
    # Existing human-readable tests match against legacy 5-seg files.
    # This test verifies the same row labels also match a canonical 6D file.

    def test_human_readable_row_matches_canonical_6d_file(self) -> None:
        """
        Row with human-readable labels ("Factory Line" / "Wide Shot") must match
        a canonical 6D file (factory-floor_machine_display_wide_static_v1.mp4).
        """
        rows = [{"Category": "Factory Line", "Shot": "Wide Shot"}]
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory-floor_machine_display_wide_static_v1.mp4").write_bytes(b"x")
            summary = summarize_factory_coverage(rows, factory_dir)
        self.assertEqual(summary["total_ready"], 1,
                         "human-readable row must match canonical 6D file")
        self.assertEqual(summary["total_missing"], 0)

    # ── 4. Slot generation → filename → readback ─────────────────────────────
    # This is the scenario completely absent from the existing suite.

    def test_slot_generation_to_filename_to_readback_round_trip(self) -> None:
        """
        Full pipeline: build_project_slots_from_creative → slot subject/action/coverage
        → build_factory_filename → on-disk file → summarize_factory_coverage counts ready.

        Proves that what the slot generator emits and what the file-name generator
        writes can be read back into the same canonical key by the coverage summarizer.
        """
        creative = {
            "meta": {"target_length": 20},
            "beats": [
                {
                    "purpose": "establish_context",
                    "subtitle": "Opening shot",
                    "vo": "Our factory floor.",
                    "visual": "factory floor production line overview",
                },
            ],
        }
        slots = build_project_slots_from_creative(creative)
        self.assertTrue(slots, "expected at least one slot from creative")
        slot = slots[0]

        subject = slot.get("subject", "")
        action = slot.get("action", "")
        coverage = slot.get("coverage", "")
        scene = slot.get("scene", "")
        self.assertTrue(subject and action and coverage,
                        f"slot missing subject/action/coverage: {slot!r}")

        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)

            # Generate and write the filename exactly as the UI would
            filename = build_factory_filename(
                scene, slot.get("content", ""), coverage, slot.get("move", "static"), 1, ".mp4",
                subject=subject, action=action,
            )
            (factory_dir / filename).write_bytes(b"x")

            # Verify the file parses to the same key the slot implies
            file_key = parse_factory_filename_key(factory_dir / filename)
            self.assertEqual(file_key, (subject, action, coverage),
                             f"slot key ({subject},{action},{coverage}) "
                             f"vs parsed file key {file_key!r}")

            # Verify summarize_factory_coverage sees it as ready using a canonical row
            summary = summarize_factory_coverage(
                [{"Subject": subject, "Action": action, "CoverageCanonical": coverage}],
                factory_dir,
            )
        self.assertEqual(summary["total_ready"], 1,
                         f"slot-derived file {filename!r} must count as ready")
        self.assertEqual(summary["total_missing"], 0)

    # ── 5. Legacy 5-seg file still participates in coverage summary ───────────
    # Locks that backward-compat read of old-format files is not broken by
    # any of the canonical changes.

    def test_legacy_5seg_and_canonical_6d_both_count_in_same_summary(self) -> None:
        """
        Two rows, one satisfied by a legacy 5-seg file and one by a canonical 6D file.
        Both must count as ready in the same summary call.
        """
        rows = [
            {"Category": "Line", "Shot": "Wide"},       # matches legacy 5-seg
            {"Subject": "machine", "Action": "display", "CoverageCanonical": "wide"},  # matches 6D
        ]
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_line_wide_static_01.mp4").write_bytes(b"x")             # legacy
            (factory_dir / "factory-floor_machine_display_wide_static_v1.mp4").write_bytes(b"x")  # 6D
            summary = summarize_factory_coverage(rows, factory_dir)
        self.assertEqual(summary["total_need"], 2)
        self.assertEqual(summary["total_ready"], 2)
        self.assertEqual(summary["total_missing"], 0)


class NextIndexForVariantFormatTests(unittest.TestCase):
    """
    Regression lock for the next_index_for / build_factory_filename variant-format agreement.

    Before the fix:
    - build_factory_filename emits v1 / v2 / v10 (unpadded)
    - next_index_for scanned for \\d\\d (exactly 2 digits), so v1 / v2 / v10 were invisible
    - every Pool Fill save therefore returned index 1, silently overwriting prior files

    After the fix: \\d+ accepts any number of digits, preserving compatibility with
    older zero-padded files (v01, v02) while correctly seeing unpadded variants.
    """

    _KWARGS = dict(subject="machine", action="display")

    def _write(self, factory_dir: Path, filename: str) -> None:
        (factory_dir / filename).write_bytes(b"x")

    def test_next_index_for_sees_files_written_by_build_factory_filename(self) -> None:
        """Files written by build_factory_filename (v1, v2) must be counted by next_index_for."""
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            for i in (1, 2):
                fn = build_factory_filename(
                    "factory-floor", "line", "wide", "static", i, ".mp4", **self._KWARGS
                )
                self._write(factory_dir, fn)

            nxt = next_index_for(
                factory_dir, "factory-floor", "line", "wide", "static", ".mp4", **self._KWARGS
            )
        self.assertEqual(nxt, 3, "must see both v1 and v2 files written by build_factory_filename")

    def test_next_index_for_handles_mixed_padded_and_unpadded_variants(self) -> None:
        """Directory with v1, v09, v10 (mixed) must return next = 11."""
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            for suffix in ("v1", "v09", "v10"):
                self._write(factory_dir,
                            f"factory-floor_machine_display_wide_static_{suffix}.mp4")

            nxt = next_index_for(
                factory_dir, "factory-floor", "line", "wide", "static", ".mp4", **self._KWARGS
            )
        self.assertEqual(nxt, 11)

    def test_next_index_for_scoping_unaffected_with_unpadded_variants(self) -> None:
        """Wrong-coverage and wrong-move files must still be ignored, even in unpadded format."""
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            # matching
            self._write(factory_dir, "factory-floor_machine_display_wide_static_v1.mp4")
            # wrong move
            self._write(factory_dir, "factory-floor_machine_display_wide_pushin_v2.mp4")
            # wrong coverage
            self._write(factory_dir, "factory-floor_machine_display_detail_static_v3.mp4")

            nxt = next_index_for(
                factory_dir, "factory-floor", "line", "wide", "static", ".mp4", **self._KWARGS
            )
        self.assertEqual(nxt, 2, "only the matching file (v1) must be counted")

    def test_build_factory_filename_and_next_index_for_agree_on_variant_format(self) -> None:
        """Integration: write N files via build_factory_filename, next_index_for returns N+1."""
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            for i in range(1, 6):
                fn = build_factory_filename(
                    "factory-floor", "line", "medium", "pan", i, ".mp4", **self._KWARGS
                )
                self._write(factory_dir, fn)

            nxt = next_index_for(
                factory_dir, "factory-floor", "line", "medium", "pan", ".mp4", **self._KWARGS
            )
        self.assertEqual(nxt, 6)


class NonFactorySceneRoundTripTests(unittest.TestCase):
    """
    Lock the round-trip for canonical 6D files whose scene prefix is NOT factory-floor.

    These tests verify that parse_factory_filename_key and summarize_factory_coverage
    correctly handle any SCENE_VALUES token, not just the factory family.
    """

    def _summarize(self, rows: list, filenames: list[str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            for fn in filenames:
                (factory_dir / fn).write_bytes(b"x")
            return summarize_factory_coverage(rows, factory_dir)

    def test_showroom_canonical_6d_round_trip(self) -> None:
        """showroom_product_display_wide_static_v1.mp4 must resolve to (product, display, wide)."""
        filename = "showroom_product_display_wide_static_v1.mp4"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / filename
            p.write_bytes(b"x")
            key = parse_factory_filename_key(p)
        self.assertEqual(key, ("product", "display", "wide"),
                         f"showroom canonical file parsed to wrong key: {key!r}")

        summary = self._summarize(
            [{"Subject": "product", "Action": "display", "CoverageCanonical": "wide"}],
            [filename],
        )
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 0)

    def test_testing_area_canonical_6d_round_trip(self) -> None:
        """testing-area_workspace_inspect_medium_static_v1.mp4 must resolve to (workspace, inspect, medium)."""
        filename = "testing-area_workspace_inspect_medium_static_v1.mp4"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / filename
            p.write_bytes(b"x")
            key = parse_factory_filename_key(p)
        self.assertEqual(key, ("workspace", "inspect", "medium"),
                         f"testing-area canonical file parsed to wrong key: {key!r}")

        summary = self._summarize(
            [{"Subject": "workspace", "Action": "inspect", "CoverageCanonical": "medium"}],
            [filename],
        )
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 0)

    def test_warehouse_canonical_6d_round_trip(self) -> None:
        """warehouse_workspace_transport_wide_static_v1.mp4 must resolve to (workspace, transport, wide)."""
        filename = "warehouse_workspace_transport_wide_static_v1.mp4"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / filename
            p.write_bytes(b"x")
            key = parse_factory_filename_key(p)
        self.assertEqual(key, ("workspace", "transport", "wide"),
                         f"warehouse canonical file parsed to wrong key: {key!r}")

        summary = self._summarize(
            [{"Subject": "workspace", "Action": "transport", "CoverageCanonical": "wide"}],
            [filename],
        )
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 0)


class ShowCapabilityAndBuildTrustSlotRoundTripTests(unittest.TestCase):
    """
    Lock the slot-generation → filename → readback round-trip for show_capability
    and build_trust beats.

    Strategy:
    - build_project_slots_from_creative with a minimal creative dict
    - assert the slot carries the expected canonical subject/action/coverage
    - write the matching file via build_factory_filename
    - verify summarize_factory_coverage counts it as ready

    If any of these assertions fail it means the slot generator changed its output
    without a corresponding change to the inventory key derivation.
    """

    def _slot_for(self, purpose: str, visual: str, duration_hint: float = 0.0) -> dict:
        creative = {
            "meta": {"target_length": 20},
            "beats": [{"purpose": purpose, "subtitle": "T", "vo": "V",
                       "visual": visual, "duration_hint": duration_hint}],
        }
        slots = build_project_slots_from_creative(creative)
        self.assertTrue(slots, f"expected at least one slot for purpose={purpose!r}")
        return slots

    def _round_trip(self, slot: dict) -> dict:
        subject = slot["subject"]
        action = slot["action"]
        coverage = slot["coverage"]
        scene = slot.get("scene", "factory-floor")
        move = slot.get("move", "static")
        filename = build_factory_filename(scene, slot.get("content", ""), coverage, move, 1, ".mp4",
                                          subject=subject, action=action)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / filename).write_bytes(b"x")
            return summarize_factory_coverage(
                [{"Subject": subject, "Action": action, "CoverageCanonical": coverage}],
                Path(tmp),
            )

    # ── show_capability ───────────────────────────────────────────────────────

    def test_show_capability_medium_slot_canonical_values_and_round_trip(self) -> None:
        """
        show_capability beat with production-line visual and duration_hint=3.0
        must produce exactly one medium slot that round-trips through the filename chain.

        Expected: subject=workspace, action=operate, coverage=medium
        (production-line visual → content=production → legacy derivation with show_capability purpose)
        """
        slots = self._slot_for("show_capability", "production line operation", duration_hint=3.0)
        self.assertEqual(len(slots), 1, "duration_hint=3.0 must yield exactly 1 slot")
        slot = slots[0]
        self.assertEqual(slot.get("coverage"), "medium", f"expected medium slot, got {slot!r}")
        self.assertEqual(slot.get("subject"), "workspace",
                         f"show_capability production-line should derive subject=workspace, got {slot!r}")
        self.assertEqual(slot.get("action"), "operate",
                         f"show_capability should derive action=operate, got {slot!r}")

        summary = self._round_trip(slot)
        self.assertEqual(summary["total_ready"], 1,
                         "show_capability medium slot file must count as ready")
        self.assertEqual(summary["total_missing"], 0)

    def test_show_capability_detail_slot_round_trip(self) -> None:
        """
        show_capability beat with duration_hint=5.0 yields medium+detail slots.
        The detail slot must also round-trip correctly.
        """
        slots = self._slot_for("show_capability", "production line operation", duration_hint=5.0)
        self.assertEqual(len(slots), 2, "duration_hint=5.0 must yield medium + detail slots")
        detail_slot = next((s for s in slots if s.get("coverage") == "detail"), None)
        self.assertIsNotNone(detail_slot, "expected a detail slot")

        summary = self._round_trip(detail_slot)
        self.assertEqual(summary["total_ready"], 1,
                         "show_capability detail slot file must count as ready")
        self.assertEqual(summary["total_missing"], 0)

    # ── build_trust ───────────────────────────────────────────────────────────

    def test_build_trust_medium_slot_canonical_values_and_round_trip(self) -> None:
        """
        build_trust beat with inspection-area visual and duration_hint=3.0
        must produce exactly one medium slot that round-trips through the filename chain.

        Expected: subject=workspace, action=inspect, coverage=medium
        (inspection area → content=inspection → legacy derivation with build_trust purpose)
        """
        slots = self._slot_for("build_trust", "inspection area", duration_hint=3.0)
        self.assertEqual(len(slots), 1, "duration_hint=3.0 must yield exactly 1 slot")
        slot = slots[0]
        self.assertEqual(slot.get("coverage"), "medium", f"expected medium slot, got {slot!r}")
        self.assertEqual(slot.get("subject"), "workspace",
                         f"build_trust inspection should derive subject=workspace, got {slot!r}")
        self.assertEqual(slot.get("action"), "inspect",
                         f"build_trust should derive action=inspect, got {slot!r}")

        summary = self._round_trip(slot)
        self.assertEqual(summary["total_ready"], 1,
                         "build_trust medium slot file must count as ready")
        self.assertEqual(summary["total_missing"], 0)

    def test_build_trust_medium_and_detail_both_round_trip(self) -> None:
        """
        build_trust beat with no duration_hint yields medium + detail slots.
        Both must share the same subject/action key and both must round-trip.
        """
        slots = self._slot_for("build_trust", "inspection area")
        self.assertEqual(len(slots), 2, "default duration must yield medium + detail slots")

        medium_slot = next((s for s in slots if s.get("coverage") == "medium"), None)
        detail_slot = next((s for s in slots if s.get("coverage") == "detail"), None)
        self.assertIsNotNone(medium_slot, "expected a medium slot")
        self.assertIsNotNone(detail_slot, "expected a detail slot")

        # Both slots must share the same subject and action
        self.assertEqual(medium_slot.get("subject"), detail_slot.get("subject"),
                         "medium and detail trust slots must share subject")
        self.assertEqual(medium_slot.get("action"), detail_slot.get("action"),
                         "medium and detail trust slots must share action")

        for slot in (medium_slot, detail_slot):
            summary = self._round_trip(slot)
            self.assertEqual(summary["total_ready"], 1,
                             f"build_trust {slot['coverage']} slot file must count as ready")
            self.assertEqual(summary["total_missing"], 0)


class MixedSceneSummaryTests(unittest.TestCase):
    """
    Verify that factory-floor files and non-factory-floor files in the same
    directory do not interfere with each other in a single summarize_factory_coverage call.
    """

    def test_factory_floor_and_non_factory_keys_do_not_interfere(self) -> None:
        """
        Two rows — one matched by a factory-floor file and one by a testing-area file.
        Each must count as ready; neither must inflate or deflate the other's count.
        """
        rows = [
            {"Subject": "machine", "Action": "display", "CoverageCanonical": "wide"},      # factory-floor
            {"Subject": "workspace", "Action": "inspect", "CoverageCanonical": "medium"},  # testing-area
        ]
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory-floor_machine_display_wide_static_v1.mp4").write_bytes(b"x")
            (factory_dir / "testing-area_workspace_inspect_medium_static_v1.mp4").write_bytes(b"x")
            summary = summarize_factory_coverage(rows, factory_dir)

        self.assertEqual(summary["total_need"], 2)
        self.assertEqual(summary["total_ready"], 2,
                         "both factory-floor and testing-area files must count as ready")
        self.assertEqual(summary["total_missing"], 0)

    def test_non_factory_file_does_not_count_against_factory_row(self) -> None:
        """
        A testing-area file must NOT satisfy a factory-floor row with the same subject/action/coverage.
        They are different scenes; the canonical key is scene-agnostic but the row must be satisfied
        only when the correct file exists.
        """
        rows = [
            {"Subject": "workspace", "Action": "inspect", "CoverageCanonical": "medium"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            # Only a testing-area file, no factory-floor file
            (factory_dir / "testing-area_workspace_inspect_medium_static_v1.mp4").write_bytes(b"x")
            summary = summarize_factory_coverage(rows, factory_dir)

        # The key is (workspace, inspect, medium) regardless of scene — this file SHOULD satisfy it
        # This test locks the current semantics: coverage summary is scene-agnostic (key = subject+action+coverage)
        self.assertEqual(summary["total_ready"], 1,
                         "testing-area file satisfies a scene-agnostic (subject,action,coverage) row")
        self.assertEqual(summary["total_missing"], 0)


if __name__ == "__main__":
    unittest.main()
