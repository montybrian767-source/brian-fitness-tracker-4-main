from pathlib import Path

import pandas as pd
import streamlit as st

from engines.smart_scale_engine import (
    BODY_COLUMNS,
    CANONICAL_IMPORT_FIELDS,
    FIELD_LABELS,
    analyze_import,
    apply_import,
    infer_column_mapping,
    read_uploaded_csv,
)
from engines.renpho_sync_engine import sync_renpho_measurements


def _read_body(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=BODY_COLUMNS)
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=BODY_COLUMNS)

    changed = False
    for col in BODY_COLUMNS:
        if col not in df.columns:
            df[col] = ""
            changed = True
    if "import_source" in df.columns:
        src = df["import_source"].astype(str)
        missing = src.str.strip().eq("") | src.str.lower().eq("nan")
        if missing.any():
            df.loc[missing, "import_source"] = "Manual"
            changed = True

    if changed:
        # Persist migration immediately for backward compatibility.
        df.to_csv(path, index=False)
    return df[BODY_COLUMNS]


def render_smart_scale_import_page(body_path: Path):
    st.markdown(
        '<div class="hero"><div class="kicker">PROJECT TITAN</div><div class="title">Smart Scale Import</div><div class="sub">Universal smart scale importer with preview, validation, and confirm-before-write protection.</div></div>',
        unsafe_allow_html=True,
    )

    existing = _read_body(body_path)

    with st.container(border=True):
        st.subheader("Renpho Cloud Sync (Optional)")
        st.caption("Uses local .env variables only: RENPHO_EMAIL and RENPHO_PASSWORD.")
        if st.button("Sync Renpho Data", key="sync_renpho_data", use_container_width=True):
            result = sync_renpho_measurements(existing)
            if not result.ok:
                if result.fallback:
                    st.info(result.message)
                else:
                    st.warning(result.message)
            else:
                out = apply_import(existing, result.candidates_df)
                out.to_csv(body_path, index=False)
                st.session_state.smart_scale_sync_summary = {
                    "message": result.message,
                    "found": result.pulled,
                    "duplicates": result.duplicates,
                    "errors": result.invalid,
                    "added": result.added,
                }
                # Ensure all pages read latest body_stats.csv immediately.
                st.rerun()

    sync_summary = st.session_state.get("smart_scale_sync_summary")
    if sync_summary:
        st.success(sync_summary["message"])
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Found", str(sync_summary["found"]))
        s2.metric("Added", str(sync_summary["added"]))
        s3.metric("Skipped Duplicates", str(sync_summary["duplicates"]))
        s4.metric("Errors", str(sync_summary["errors"]))

    st.markdown("---")
    st.markdown("### CSV Smart Scale Import (Backup)")
    uploaded = st.file_uploader("CSV file selector", type=["csv"], key="smart_scale_uploader")

    if uploaded is None:
        st.info("Upload a smart scale CSV to begin analysis.")
        return

    try:
        imported_raw = read_uploaded_csv(uploaded.getvalue())
    except Exception as exc:
        st.error(f"Could not parse CSV: {exc}")
        return

    if imported_raw.empty:
        st.warning("The uploaded file is empty.")
        return

    auto_mapping, _ = infer_column_mapping(list(imported_raw.columns))

    normalized_headers = {str(c).strip().lower() for c in imported_raw.columns}
    renpho_signatures = {
        "weight(lb)",
        "muscle mass(lb)",
        "body fat(%)",
        "body water(%)",
        "protein (%)",
        "visceral fat",
        "bmr(kcal)",
        "metabolic age",
        "bone mass(lb)",
        "bmi",
    }
    default_import_source_index = 1 if renpho_signatures.issubset(normalized_headers) else 5

    st.markdown("### Column Mapping")
    st.caption("Auto-mapping is applied first. Use manual mapping for any missing field.")
    manual_mapping = dict(auto_mapping)

    import_source = st.selectbox(
        "Import Source",
        ["Manual", "RENPHO", "Eufy", "Withings", "Garmin", "CSV Import", "Unknown"],
        index=default_import_source_index,
        key="smart_scale_import_source",
    )

    cols = st.columns(2)
    for idx, target in enumerate(CANONICAL_IMPORT_FIELDS):
        with cols[idx % 2]:
            choices = ["<unmapped>"] + list(imported_raw.columns)
            default_src = auto_mapping.get(target, "<unmapped>")
            default_ix = choices.index(default_src) if default_src in choices else 0
            selected = st.selectbox(
                f"{FIELD_LABELS.get(target, target)}",
                choices,
                index=default_ix,
                key=f"map_{target}",
            )
            if selected != "<unmapped>":
                manual_mapping[target] = selected
            elif target in manual_mapping:
                manual_mapping.pop(target, None)

    if "date" not in manual_mapping or "body_weight_lbs" not in manual_mapping:
        st.warning("Date and Weight mappings are required to import.")
        return

    if st.button("Import Smart Scale Data", use_container_width=True):
        preview = analyze_import(imported_raw, existing, manual_mapping, import_source=import_source)
        st.session_state.smart_scale_preview = {
            "mapping": manual_mapping,
            "import_source": import_source,
            "records_found": preview.records_found,
            "date_range": preview.date_range,
            "duplicate_entries": preview.duplicate_entries,
            "new_entries": preview.new_entries,
            "invalid_rows": preview.invalid_rows,
            "preview_df": preview.preview_df,
            "candidates_df": preview.candidates_df,
        }

    preview_state = st.session_state.get("smart_scale_preview")
    if not preview_state:
        st.info("Click Import Smart Scale Data to analyze and preview before saving.")
        return

    st.markdown("### Import Analysis")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Number of records found", str(preview_state["records_found"]))
    c2.metric("Date range", preview_state["date_range"])
    c3.metric("Duplicate entries detected", str(preview_state["duplicate_entries"]))
    c4.metric("New entries that will be added", str(preview_state["new_entries"]))
    st.caption(f"Import source: {preview_state.get('import_source', 'Unknown')}")

    if preview_state["invalid_rows"]:
        st.warning(f"Invalid rows skipped: {preview_state['invalid_rows']}")

    st.markdown("### Sample Preview (first 10 rows)")
    if preview_state["preview_df"].empty:
        st.info("No new rows to add after duplicate and validation checks.")
    else:
        st.dataframe(preview_state["preview_df"].head(10), use_container_width=True, hide_index=True)

    if st.button("Confirm Import", type="primary", use_container_width=True):
        candidates_df = preview_state["candidates_df"]
        if candidates_df.empty:
            st.info("Nothing new to import.")
            return

        out = apply_import(existing, candidates_df)
        out.to_csv(body_path, index=False)
        st.success(f"Import complete. Added {len(candidates_df)} new entries to body_stats.csv.")
        st.session_state.pop("smart_scale_preview", None)
