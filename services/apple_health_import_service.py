from __future__ import annotations

import hashlib
import shutil
import tempfile
import time
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from services.supabase_service import connect_supabase


APPLE_ACTIVITY_COLUMNS = [
    'activity_date',
    'steps',
    'active_energy_kcal',
    'active_energy_goal_kcal',
    'basal_energy_kcal',
    'exercise_minutes',
    'exercise_goal_minutes',
    'stand_hours',
    'stand_goal_hours',
    'walking_running_distance_miles',
    'flights_climbed',
    'resting_heart_rate',
    'walking_heart_rate_average',
    'heart_rate_variability_ms',
    'average_heart_rate',
    'maximum_heart_rate',
    'sleep_hours',
    'source',
    'imported_at',
]

APPLE_WORKOUT_COLUMNS = [
    'apple_workout_key',
    'workout_type',
    'start_time',
    'end_time',
    'duration_minutes',
    'total_energy_kcal',
    'total_distance_miles',
    'average_heart_rate',
    'maximum_heart_rate',
    'source_name',
    'source_version',
    'device',
    'metadata',
    'imported_at',
]

DAILY_READINESS_COLUMNS = [
    'readiness_date',
    'readiness_score',
    'recovery_status',
    'confidence_score',
    'sleep_score',
    'hrv_score',
    'resting_hr_score',
    'activity_load_score',
    'strength_load_score',
    'recovery_balance_score',
    'recommendation',
    'limiting_factors',
    'positive_factors',
    'data_quality',
    'calculated_at',
]

LAST_IMPORT_STATE_KEY = 'apple_health_last_import_result'
IMPORT_RUNNING_STATE_KEY = 'apple_health_import_in_progress'

UPLOAD_CHUNK_BYTES = 2 * 1024 * 1024
SAVE_BATCH_SIZE = 100
DEFAULT_IMPORT_TIMEOUT_SECONDS = 60 * 60 * 2

SUPPORTED_RECORD_TYPES = {
    'HKQuantityTypeIdentifierStepCount',
    'HKQuantityTypeIdentifierActiveEnergyBurned',
    'HKQuantityTypeIdentifierBasalEnergyBurned',
    'HKQuantityTypeIdentifierAppleExerciseTime',
    'HKQuantityTypeIdentifierAppleStandTime',
    'HKQuantityTypeIdentifierDistanceWalkingRunning',
    'HKQuantityTypeIdentifierFlightsClimbed',
    'HKQuantityTypeIdentifierHeartRate',
    'HKQuantityTypeIdentifierRestingHeartRate',
    'HKQuantityTypeIdentifierWalkingHeartRateAverage',
    'HKQuantityTypeIdentifierHeartRateVariabilitySDNN',
    'HKCategoryTypeIdentifierSleepAnalysis',
}

WORKOUT_TYPE_LABELS = {
    'HKWorkoutActivityTypeTraditionalStrengthTraining': 'Traditional Strength Training',
    'HKWorkoutActivityTypeFunctionalStrengthTraining': 'Functional Strength Training',
    'HKWorkoutActivityTypeWalking': 'Walking',
    'HKWorkoutActivityTypeRunning': 'Running',
    'HKWorkoutActivityTypeCycling': 'Cycling',
    'HKWorkoutActivityTypePickleball': 'Pickleball',
    'HKWorkoutActivityTypeTennis': 'Tennis',
    'HKWorkoutActivityTypeHighIntensityIntervalTraining': 'HIIT',
    'HKWorkoutActivityTypeElliptical': 'Elliptical',
    'HKWorkoutActivityTypeStairClimbing': 'Stair Stepper',
    'HKWorkoutActivityTypeRowing': 'Rowing',
    'HKWorkoutActivityTypeSwimming': 'Swimming',
}


def _to_text(value: Any, default: str = '') -> str:
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    return str(value)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def _parse_timestamp(value: Any) -> Optional[pd.Timestamp]:
    if value is None:
        return None
    ts = pd.to_datetime(_to_text(value).strip(), errors='coerce', utc=True)
    if pd.isna(ts):
        return None
    return ts.tz_convert(None)


def _parse_date(value: Any) -> Optional[str]:
    ts = _parse_timestamp(value)
    if ts is None:
        return None
    return ts.date().isoformat()


def _parse_duration_minutes(start_time: Any, end_time: Any) -> float:
    start_ts = _parse_timestamp(start_time)
    end_ts = _parse_timestamp(end_time)
    if start_ts is None or end_ts is None:
        return 0.0
    return max(0.0, (end_ts - start_ts).total_seconds() / 60.0)


def _parse_energy_kcal(value: Any, unit: Any) -> float:
    amount = _to_float(value, 0.0)
    unit_text = _to_text(unit).strip().lower()
    if unit_text in {'kj', 'kilojoule', 'kilojoules'}:
        return amount * 0.239005736
    return amount


def _parse_distance_miles(value: Any, unit: Any) -> float:
    amount = _to_float(value, 0.0)
    unit_text = _to_text(unit).strip().lower()
    if unit_text in {'m', 'meter', 'meters'}:
        return amount / 1609.344
    if unit_text in {'km', 'kilometer', 'kilometers'}:
        return amount * 0.621371
    if unit_text in {'ft', 'feet'}:
        return amount / 5280.0
    return amount


def _parse_minutes(value: Any, unit: Any) -> float:
    amount = _to_float(value, 0.0)
    unit_text = _to_text(unit).strip().lower()
    if unit_text in {'hr', 'hour', 'hours'}:
        return amount * 60.0
    if unit_text in {'s', 'sec', 'secs', 'second', 'seconds'}:
        return amount / 60.0
    return amount


def _parse_hours(value: Any, unit: Any) -> float:
    amount = _to_float(value, 0.0)
    unit_text = _to_text(unit).strip().lower()
    if unit_text in {'min', 'minute', 'minutes'}:
        return amount / 60.0
    if unit_text in {'s', 'sec', 'secs', 'second', 'seconds'}:
        return amount / 3600.0
    return amount


def _preferred_source_rank(record: Dict[str, Any]) -> int:
    source = f"{record.get('source_name', '')} {record.get('device', '')}".lower()
    if 'watch' in source:
        return 3
    if 'iphone' in source or 'ios' in source or 'phone' in source:
        return 2
    return 1


def _sleep_state_value(value: str) -> bool:
    text = value.lower()
    return 'asleep' in text and 'inbed' not in text and 'awake' not in text


def _normalize_workout_type(raw_type: str) -> str:
    friendly = WORKOUT_TYPE_LABELS.get(raw_type, '')
    if friendly:
        return friendly
    cleaned = _to_text(raw_type).replace('HKWorkoutActivityType', '').strip()
    return cleaned or 'Other'


def _xml_path_from_source(xml_source: Any) -> Tuple[Optional[Path], Optional[Path]]:
    if isinstance(xml_source, Path):
        return xml_source, None
    if isinstance(xml_source, str):
        return Path(xml_source), None

    temp_dir = Path(tempfile.mkdtemp(prefix='apple_health_source_'))
    temp_path = temp_dir / 'export.xml'
    with open(temp_path, 'wb') as temp_file:
        try:
            xml_source.seek(0)
        except Exception:
            pass
        shutil.copyfileobj(xml_source, temp_file)
    return temp_path, temp_dir


def _safe_uploaded_size(uploaded_file: Any) -> int:
    try:
        return int(getattr(uploaded_file, 'size', 0) or 0)
    except Exception:
        return 0


def _init_import_state(uploaded_file: Any) -> Dict[str, Any]:
    return {
        'ok': False,
        'stage': 'starting',
        'import_source': _to_text(getattr(uploaded_file, 'name', 'Apple Health Export')).strip() or 'Apple Health Export',
        'zip_uploaded_bytes': 0,
        'zip_uploaded_mb': 0.0,
        'export_xml_size_bytes': 0,
        'records_processed': 0,
        'supported_records_found': 0,
        'workouts_found': 0,
        'days_summarized': 0,
        'daily_rows_saved': 0,
        'workout_rows_saved': 0,
        'records_seen': 0,
        'records_ignored': 0,
        'daily_records_added': 0,
        'daily_records_updated': 0,
        'apple_workouts_added': 0,
        'duplicate_workouts_skipped': 0,
        'errors': [],
        'date_range': 'No data',
        'completed_at': '',
        'duration_seconds': 0.0,
        'input_size_bytes': _safe_uploaded_size(uploaded_file),
        'status_message': 'Preparing import.',
    }


def _commit_import_state(state: Dict[str, Any], callback: Optional[Callable[[Dict[str, Any]], None]] = None):
    st.session_state[LAST_IMPORT_STATE_KEY] = dict(state)
    if callback is not None:
        try:
            callback(dict(state))
        except Exception:
            pass


def _update_import_state(
    state: Dict[str, Any],
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    stage: Optional[str] = None,
    status_message: Optional[str] = None,
    **updates: Any,
):
    if stage is not None:
        state['stage'] = stage
    if status_message is not None:
        state['status_message'] = status_message
    for key, value in updates.items():
        state[key] = value
    _commit_import_state(state, callback)


def _stream_upload_to_named_temp(uploaded_file: Any, callback: Optional[Callable[[Dict[str, Any]], None]] = None, state: Optional[Dict[str, Any]] = None) -> Path:
    if uploaded_file is None:
        raise ValueError('No file uploaded.')

    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip', prefix='apple_health_upload_')
    temp_zip_path = Path(temp_zip.name)
    bytes_written = 0

    try:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

        while True:
            chunk = uploaded_file.read(UPLOAD_CHUNK_BYTES)
            if not chunk:
                break
            temp_zip.write(chunk)
            bytes_written += len(chunk)
            if state is not None:
                _update_import_state(
                    state,
                    callback,
                    stage='zip_uploaded',
                    status_message='ZIP uploaded to temporary disk file.',
                    zip_uploaded_bytes=int(bytes_written),
                    zip_uploaded_mb=round(bytes_written / (1024 * 1024), 2),
                )

        temp_zip.flush()
        return temp_zip_path
    finally:
        temp_zip.close()


def _new_daily_row(activity_date: str) -> Dict[str, Any]:
    return {
        'activity_date': activity_date,
        'steps': 0.0,
        'active_energy_kcal': 0.0,
        'active_energy_goal_kcal': None,
        'basal_energy_kcal': 0.0,
        'exercise_minutes': 0.0,
        'exercise_goal_minutes': None,
        'stand_hours': 0.0,
        'stand_goal_hours': None,
        'walking_running_distance_miles': 0.0,
        'flights_climbed': 0.0,
        'resting_heart_rate': None,
        'walking_heart_rate_average': None,
        'heart_rate_variability_ms': None,
        'average_heart_rate': None,
        'maximum_heart_rate': None,
        'sleep_hours': None,
        'source': 'Apple Health',
        'imported_at': datetime.now(timezone.utc).isoformat(),
    }


def _add_avg_metric(bucket: Dict[str, Dict[str, float]], day: str, field: str, value: float):
    k = f'{day}|{field}'
    item = bucket.get(k)
    if item is None:
        bucket[k] = {'sum': float(value), 'count': 1.0}
        return
    item['sum'] += float(value)
    item['count'] += 1.0


def _apply_avg_metrics(rows_by_date: Dict[str, Dict[str, Any]], avg_bucket: Dict[str, Dict[str, float]]):
    for key, val in avg_bucket.items():
        day, field = key.split('|', 1)
        row = rows_by_date.get(day)
        if not row:
            continue
        count = float(val.get('count', 0) or 0)
        if count <= 0:
            continue
        row[field] = round(float(val.get('sum', 0.0) or 0.0) / count, 1)


def _save_daily_activity_batch(client: Any, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {'ok': True, 'saved': 0, 'errors': []}
    try:
        payload = [_clean_payload(r, APPLE_ACTIVITY_COLUMNS) for r in rows]
        client.table('apple_activity_daily').upsert(payload, on_conflict='activity_date').execute()
        return {'ok': True, 'saved': len(payload), 'errors': []}
    except Exception as exc:
        return {'ok': False, 'saved': 0, 'errors': [{'error': str(exc)}]}


def _save_workout_batch(client: Any, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {'ok': True, 'saved': 0, 'errors': []}
    try:
        payload = [_clean_payload(r, APPLE_WORKOUT_COLUMNS) for r in rows]
        # Upsert keeps imports duplicate-safe by workout hash key.
        client.table('apple_workouts').upsert(payload, on_conflict='apple_workout_key').execute()
        return {'ok': True, 'saved': len(payload), 'errors': []}
    except Exception as exc:
        return {'ok': False, 'saved': 0, 'errors': [{'error': str(exc)}]}


def extract_export_xml(uploaded_file: Any) -> Tuple[Optional[Path], Optional[str]]:
    if uploaded_file is None:
        return None, 'No file uploaded.'

    file_name = _to_text(getattr(uploaded_file, 'name', '')).strip().lower()
    temp_dir = Path(tempfile.mkdtemp(prefix='apple_health_import_'))
    target_path = temp_dir / 'export.xml'

    try:
        if file_name.endswith('.zip'):
            with zipfile.ZipFile(uploaded_file) as archive:
                member = next((info for info in archive.infolist() if info.filename.lower().endswith('export.xml')), None)
                if member is None:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return None, 'export.xml was not found inside the ZIP archive.'
                with archive.open(member) as source, open(target_path, 'wb') as destination:
                    shutil.copyfileobj(source, destination)
            return target_path, None

        if file_name.endswith('.xml'):
            with open(target_path, 'wb') as destination:
                try:
                    uploaded_file.seek(0)
                except Exception:
                    pass
                shutil.copyfileobj(uploaded_file, destination)
            return target_path, None

        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, 'Only .zip and .xml files are supported.'
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, str(exc)


def parse_health_records(xml_source: Any) -> Iterator[Dict[str, Any]]:
    source_path, cleanup_dir = _xml_path_from_source(xml_source)
    if source_path is None:
        return

    try:
        for _, element in ET.iterparse(str(source_path), events=('end',)):
            tag = _local_name(element.tag)
            attrs = dict(element.attrib)

            if tag == 'Record':
                record_type = _to_text(attrs.get('type', '')).strip()
                if record_type not in SUPPORTED_RECORD_TYPES:
                    element.clear()
                    continue

                start_time = attrs.get('startDate')
                end_time = attrs.get('endDate')
                activity_date = _parse_date(start_time or end_time or attrs.get('creationDate'))
                yield {
                    'kind': 'record',
                    'record_type': record_type,
                    'activity_date': activity_date,
                    'start_time': _parse_timestamp(start_time),
                    'end_time': _parse_timestamp(end_time),
                    'source_name': _to_text(attrs.get('sourceName', 'Apple Health')),
                    'source_version': _to_text(attrs.get('sourceVersion', '')),
                    'device': _to_text(attrs.get('device', '')),
                    'unit': _to_text(attrs.get('unit', ''), ''),
                    'value': _to_text(attrs.get('value', ''), ''),
                    'numeric_value': _to_float(attrs.get('value', 0.0), 0.0),
                    'metadata': attrs,
                }

            elif tag == 'ActivitySummary':
                summary_date = _parse_date(attrs.get('dateComponents') or attrs.get('startDate') or attrs.get('date') or attrs.get('endDate'))
                if summary_date:
                    yield {
                        'kind': 'activity_summary',
                        'activity_date': summary_date,
                        'active_energy_kcal': _parse_energy_kcal(attrs.get('activeEnergyBurned') or attrs.get('activeEnergy'), attrs.get('energyUnit', attrs.get('unit', 'kcal'))),
                        'active_energy_goal_kcal': _parse_energy_kcal(attrs.get('activeEnergyBurnedGoal') or attrs.get('activeEnergyGoal'), attrs.get('energyUnit', attrs.get('unit', 'kcal'))),
                        'exercise_minutes': _parse_minutes(attrs.get('appleExerciseTime') or attrs.get('exerciseTime'), attrs.get('exerciseTimeUnit', attrs.get('unit', 'min'))),
                        'exercise_goal_minutes': _parse_minutes(attrs.get('appleExerciseTimeGoal') or attrs.get('exerciseTimeGoal'), attrs.get('exerciseTimeUnit', attrs.get('unit', 'min'))),
                        'stand_hours': _parse_hours(attrs.get('appleStandHours') or attrs.get('standHours'), attrs.get('standHoursUnit', attrs.get('unit', 'hr'))),
                        'stand_goal_hours': _parse_hours(attrs.get('appleStandHoursGoal') or attrs.get('standHoursGoal'), attrs.get('standHoursUnit', attrs.get('unit', 'hr'))),
                        'source_name': _to_text(attrs.get('sourceName', 'Apple Health')),
                        'metadata': attrs,
                    }

            element.clear()
    finally:
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def parse_apple_workouts(xml_source: Any) -> Iterator[Dict[str, Any]]:
    source_path, cleanup_dir = _xml_path_from_source(xml_source)
    if source_path is None:
        return

    try:
        for _, element in ET.iterparse(str(source_path), events=('end',)):
            tag = _local_name(element.tag)
            if tag != 'Workout':
                element.clear()
                continue

            attrs = dict(element.attrib)
            workout_type_raw = _to_text(attrs.get('workoutActivityType') or attrs.get('activityType') or attrs.get('type'), 'Other')
            workout_type = _normalize_workout_type(workout_type_raw)
            start_time = attrs.get('startDate')
            end_time = attrs.get('endDate')
            source_name = _to_text(attrs.get('sourceName', 'Apple Health'))
            source_version = _to_text(attrs.get('sourceVersion', ''))
            device = _to_text(attrs.get('device', ''))

            metadata: Dict[str, Any] = {
                'raw_workout_type': workout_type_raw,
                'duration_minutes': _parse_duration_minutes(start_time, end_time),
                'total_energy_unit': _to_text(attrs.get('totalEnergyBurnedUnit', 'kcal')),
                'total_distance_unit': _to_text(attrs.get('totalDistanceUnit', 'mi')),
            }

            for child in list(element):
                if _local_name(child.tag) == 'MetadataEntry':
                    meta_key = _to_text(child.attrib.get('key', '')).strip()
                    meta_value = child.attrib.get('value')
                    if meta_key:
                        metadata[meta_key] = meta_value

            yield {
                'apple_workout_key': build_apple_workout_key({
                    'workout_type': workout_type,
                    'start_time': start_time,
                    'end_time': end_time,
                    'source_name': source_name,
                    'device': device,
                }),
                'workout_type': workout_type,
                'start_time': _parse_timestamp(start_time),
                'end_time': _parse_timestamp(end_time),
                'duration_minutes': _parse_duration_minutes(start_time, end_time),
                'total_energy_kcal': _parse_energy_kcal(attrs.get('totalEnergyBurned'), attrs.get('totalEnergyBurnedUnit', 'kcal')),
                'total_distance_miles': _parse_distance_miles(attrs.get('totalDistance'), attrs.get('totalDistanceUnit', 'mi')),
                'average_heart_rate': _to_float(attrs.get('averageHeartRate', attrs.get('avgHeartRate')), 0.0) or None,
                'maximum_heart_rate': _to_float(attrs.get('maximumHeartRate', attrs.get('maxHeartRate')), 0.0) or None,
                'source_name': source_name,
                'source_version': source_version,
                'device': device,
                'metadata': metadata,
            }
            element.clear()
    finally:
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def aggregate_daily_activity(records: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rows_by_date: Dict[str, Dict[str, Any]] = {}
    metric_buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    stats = {
        'records_seen': 0,
        'records_used': 0,
        'records_ignored': 0,
        'activity_summary_count': 0,
        'source_names': set(),
        'date_min': None,
        'date_max': None,
    }

    def row_for(activity_date: str) -> Dict[str, Any]:
        if activity_date not in rows_by_date:
            rows_by_date[activity_date] = {
                'activity_date': activity_date,
                'steps': 0.0,
                'active_energy_kcal': 0.0,
                'active_energy_goal_kcal': None,
                'basal_energy_kcal': 0.0,
                'exercise_minutes': 0.0,
                'exercise_goal_minutes': None,
                'stand_hours': 0.0,
                'stand_goal_hours': None,
                'walking_running_distance_miles': 0.0,
                'flights_climbed': 0.0,
                'resting_heart_rate': None,
                'walking_heart_rate_average': None,
                'heart_rate_variability_ms': None,
                'average_heart_rate': None,
                'maximum_heart_rate': None,
                'sleep_hours': None,
                'source': 'Apple Health',
                'imported_at': datetime.now(timezone.utc).isoformat(),
            }
        return rows_by_date[activity_date]

    for item in records:
        stats['records_seen'] += 1
        item_kind = _to_text(item.get('kind', 'record'))
        activity_date = _to_text(item.get('activity_date', '')).strip()
        if not activity_date:
            stats['records_ignored'] += 1
            continue

        row = row_for(activity_date)
        stats['date_min'] = activity_date if stats['date_min'] is None else min(stats['date_min'], activity_date)
        stats['date_max'] = activity_date if stats['date_max'] is None else max(stats['date_max'], activity_date)

        if item_kind == 'activity_summary':
            stats['activity_summary_count'] += 1
            if item.get('active_energy_kcal') is not None:
                row['active_energy_kcal'] = float(item['active_energy_kcal'])
            if item.get('active_energy_goal_kcal') is not None:
                row['active_energy_goal_kcal'] = float(item['active_energy_goal_kcal'])
            if item.get('exercise_minutes') is not None:
                row['exercise_minutes'] = float(item['exercise_minutes'])
            if item.get('exercise_goal_minutes') is not None:
                row['exercise_goal_minutes'] = float(item['exercise_goal_minutes'])
            if item.get('stand_hours') is not None:
                row['stand_hours'] = float(item['stand_hours'])
            if item.get('stand_goal_hours') is not None:
                row['stand_goal_hours'] = float(item['stand_goal_hours'])
            source_name = _to_text(item.get('source_name', 'Apple Health')).strip()
            if source_name:
                stats['source_names'].add(source_name)
            continue

        record_type = _to_text(item.get('record_type', '')).strip()
        if record_type not in SUPPORTED_RECORD_TYPES:
            stats['records_ignored'] += 1
            continue

        metric_buckets[(activity_date, record_type)].append(item)

    for (activity_date, record_type), grouped_records in metric_buckets.items():
        if not grouped_records:
            continue

        row = row_for(activity_date)
        selected_rank = max(_preferred_source_rank(rec) for rec in grouped_records)
        selected_records = [rec for rec in grouped_records if _preferred_source_rank(rec) == selected_rank]
        stats['records_used'] += len(selected_records)

        for selected in selected_records:
            source_name = _to_text(selected.get('source_name', 'Apple Health')).strip()
            if source_name:
                stats['source_names'].add(source_name)

        values = [float(_to_float(rec.get('numeric_value', rec.get('value', 0)), 0.0)) for rec in selected_records]

        if record_type == 'HKQuantityTypeIdentifierStepCount':
            row['steps'] += sum(values)
        elif record_type == 'HKQuantityTypeIdentifierActiveEnergyBurned':
            row['active_energy_kcal'] += sum(_parse_energy_kcal(rec.get('value'), rec.get('unit', 'kcal')) for rec in selected_records)
        elif record_type == 'HKQuantityTypeIdentifierBasalEnergyBurned':
            row['basal_energy_kcal'] += sum(_parse_energy_kcal(rec.get('value'), rec.get('unit', 'kcal')) for rec in selected_records)
        elif record_type == 'HKQuantityTypeIdentifierAppleExerciseTime':
            row['exercise_minutes'] += sum(_parse_minutes(rec.get('value'), rec.get('unit', 'min')) for rec in selected_records)
        elif record_type == 'HKQuantityTypeIdentifierAppleStandTime':
            row['stand_hours'] += sum(_parse_hours(rec.get('value'), rec.get('unit', 'hr')) for rec in selected_records)
        elif record_type == 'HKQuantityTypeIdentifierDistanceWalkingRunning':
            row['walking_running_distance_miles'] += sum(_parse_distance_miles(rec.get('value'), rec.get('unit', 'mi')) for rec in selected_records)
        elif record_type == 'HKQuantityTypeIdentifierFlightsClimbed':
            row['flights_climbed'] += sum(values)
        elif record_type == 'HKQuantityTypeIdentifierRestingHeartRate':
            row['resting_heart_rate'] = round(sum(values) / len(values), 1)
        elif record_type == 'HKQuantityTypeIdentifierWalkingHeartRateAverage':
            row['walking_heart_rate_average'] = round(sum(values) / len(values), 1)
        elif record_type == 'HKQuantityTypeIdentifierHeartRateVariabilitySDNN':
            row['heart_rate_variability_ms'] = round(sum(values) / len(values), 1)
        elif record_type == 'HKQuantityTypeIdentifierHeartRate':
            row['average_heart_rate'] = round(sum(values) / len(values), 1)
            row['maximum_heart_rate'] = round(max(values), 1)
        elif record_type == 'HKCategoryTypeIdentifierSleepAnalysis':
            sleep_values = []
            for rec in selected_records:
                state = _to_text(rec.get('value', '')).strip()
                if not state or not _sleep_state_value(state):
                    continue
                duration = _parse_duration_minutes(rec.get('start_time'), rec.get('end_time')) / 60.0
                if duration > 0:
                    sleep_values.append(duration)
            if sleep_values:
                row['sleep_hours'] = round((row.get('sleep_hours') or 0) + sum(sleep_values), 2)

    daily_rows = sorted(rows_by_date.values(), key=lambda row: row['activity_date'])
    if stats['source_names']:
        sources = sorted({str(source) for source in stats['source_names'] if str(source).strip()})
        for row in daily_rows:
            row['source'] = ', '.join(sources[:3]) if sources else 'Apple Health'
    else:
        for row in daily_rows:
            row['source'] = 'Apple Health'

    stats['date_range'] = f"{stats['date_min']} to {stats['date_max']}" if stats['date_min'] and stats['date_max'] else 'No data'
    stats['records_seen'] = int(stats['records_seen'])
    stats['records_used'] = int(stats['records_used'] + stats['activity_summary_count'])
    stats['records_ignored'] = int(max(0, stats['records_seen'] - stats['records_used']))
    return daily_rows, stats


def build_apple_workout_key(workout: Dict[str, Any]) -> str:
    seed = '|'.join([
        _to_text(workout.get('workout_type', 'Other')).strip().lower(),
        _to_text(workout.get('start_time', '')).strip(),
        _to_text(workout.get('end_time', '')).strip(),
        _to_text(workout.get('source_name', '')).strip().lower(),
        _to_text(workout.get('device', '')).strip().lower(),
    ])
    return hashlib.sha256(seed.encode('utf-8')).hexdigest()


def _clean_payload(row: Dict[str, Any], columns: List[str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for column in columns:
        value = row.get(column)
        if isinstance(value, pd.Timestamp):
            payload[column] = value.to_pydatetime().isoformat()
        elif hasattr(value, 'isoformat') and not isinstance(value, (str, bytes)):
            payload[column] = value.isoformat()
        elif isinstance(value, (dict, list)):
            payload[column] = value
        elif value is None:
            payload[column] = None
        elif isinstance(value, float) and pd.isna(value):
            payload[column] = None
        else:
            payload[column] = value
    return payload


def save_daily_activity(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {'ok': True, 'added': 0, 'updated': 0, 'duplicate_skipped': 0, 'errors': []}

    client, err = connect_supabase()
    if err:
        return {'ok': False, 'added': 0, 'updated': 0, 'duplicate_skipped': 0, 'errors': [{'error': str(err)}]}

    added = 0
    updated = 0
    errors: List[Dict[str, Any]] = []

    for index, row in enumerate(rows):
        try:
            payload = _clean_payload(row, APPLE_ACTIVITY_COLUMNS)
            activity_date = _to_text(payload.get('activity_date', '')).strip()
            if not activity_date:
                raise ValueError('activity_date is required')

            existing = client.table('apple_activity_daily').select('id').eq('activity_date', activity_date).limit(1).execute()
            existed = bool(existing.data)
            client.table('apple_activity_daily').upsert(payload, on_conflict='activity_date').execute()
            if existed:
                updated += 1
            else:
                added += 1
        except Exception as exc:
            errors.append({'index': index, 'error': str(exc), 'row': row})

    return {'ok': not errors, 'added': added, 'updated': updated, 'duplicate_skipped': 0, 'errors': errors}


def save_apple_workouts(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {'ok': True, 'added': 0, 'duplicate_skipped': 0, 'errors': []}

    client, err = connect_supabase()
    if err:
        return {'ok': False, 'added': 0, 'duplicate_skipped': 0, 'errors': [{'error': str(err)}]}

    added = 0
    duplicate_skipped = 0
    errors: List[Dict[str, Any]] = []

    for index, row in enumerate(rows):
        try:
            payload = _clean_payload(row, APPLE_WORKOUT_COLUMNS)
            workout_key = _to_text(payload.get('apple_workout_key', '')).strip()
            if not workout_key:
                raise ValueError('apple_workout_key is required')

            existing = client.table('apple_workouts').select('id').eq('apple_workout_key', workout_key).limit(1).execute()
            if existing.data:
                duplicate_skipped += 1
                continue

            client.table('apple_workouts').insert(payload).execute()
            added += 1
        except Exception as exc:
            errors.append({'index': index, 'error': str(exc), 'row': row})

    return {'ok': not errors, 'added': added, 'duplicate_skipped': duplicate_skipped, 'errors': errors}


def get_apple_activity_daily() -> Tuple[pd.DataFrame, Optional[str]]:
    client, err = connect_supabase()
    if err:
        return pd.DataFrame(columns=APPLE_ACTIVITY_COLUMNS), str(err)

    try:
        response = client.table('apple_activity_daily').select('*').order('activity_date', desc=False).execute()
        return pd.DataFrame(response.data or [], columns=APPLE_ACTIVITY_COLUMNS), None
    except Exception as exc:
        return pd.DataFrame(columns=APPLE_ACTIVITY_COLUMNS), str(exc)


def _normalize_filter_workout_type(workout_type: Optional[str]) -> Optional[str]:
    text = _to_text(workout_type).strip()
    if not text or text.lower() == 'all':
        return None
    return text


def _parse_filter_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors='coerce')
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def get_apple_workouts(
    date_from: Any = None,
    date_to: Any = None,
    workout_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    min_duration_minutes: Optional[float] = None,
    has_calories: Optional[bool] = None,
    has_distance: Optional[bool] = None,
    has_heart_rate: Optional[bool] = None,
) -> Tuple[List[Dict[str, Any]], Optional[int], Optional[str]]:
    client, err = connect_supabase()
    if err:
        return [], None, str(err)

    start_from = _parse_filter_date(date_from)
    start_to = _parse_filter_date(date_to)
    workout_type_filter = _normalize_filter_workout_type(workout_type)
    page_size = max(1, min(200, int(limit or 50)))
    page_offset = max(0, int(offset or 0))

    def _apply_filters(query):
        if start_from:
            query = query.gte('start_time', f'{start_from}T00:00:00+00:00')
        if start_to:
            query = query.lt('start_time', f'{start_to}T23:59:59.999999+00:00')
        if workout_type_filter:
            if workout_type_filter.lower() == 'other':
                known = list(WORKOUT_TYPE_LABELS.values())
                query = query.not_.in_('workout_type', known)
            else:
                query = query.eq('workout_type', workout_type_filter)
        if min_duration_minutes is not None:
            query = query.gte('duration_minutes', float(min_duration_minutes))
        if has_calories:
            query = query.gt('total_energy_kcal', 0)
        if has_distance:
            query = query.gt('total_distance_miles', 0)
        if has_heart_rate:
            query = query.gt('average_heart_rate', 0)
        return query

    total_count: Optional[int] = None
    count_error: Optional[str] = None
    try:
        count_query = client.table('apple_workouts').select('id', count='exact', head=True)
        count_query = _apply_filters(count_query)
        count_response = count_query.execute()
        total_count = int(count_response.count or 0)
    except Exception as exc:
        count_error = str(exc)

    try:
        data_query = client.table('apple_workouts').select('*')
        data_query = _apply_filters(data_query)
        response = data_query.order('start_time', desc=True).range(page_offset, page_offset + page_size - 1).execute()
        rows = list(response.data or [])
        if total_count is None and rows:
            total_count = page_offset + len(rows)
        if count_error:
            return rows, total_count, f'count_query_failed: {count_error}'
        return rows, total_count, None
    except Exception as exc:
        return [], total_count, str(exc)


def get_apple_workouts_dataframe(
    date_from: Any = None,
    date_to: Any = None,
    workout_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    min_duration_minutes: Optional[float] = None,
    has_calories: Optional[bool] = None,
    has_distance: Optional[bool] = None,
    has_heart_rate: Optional[bool] = None,
) -> Tuple[pd.DataFrame, Optional[int], Optional[str]]:
    rows, total_count, err = get_apple_workouts(
        date_from=date_from,
        date_to=date_to,
        workout_type=workout_type,
        limit=limit,
        offset=offset,
        min_duration_minutes=min_duration_minutes,
        has_calories=has_calories,
        has_distance=has_distance,
        has_heart_rate=has_heart_rate,
    )
    return pd.DataFrame(rows or [], columns=APPLE_WORKOUT_COLUMNS), total_count, err


def get_apple_workouts_total_count() -> Tuple[int, Optional[str]]:
    client, err = connect_supabase()
    if err:
        return 0, str(err)
    try:
        response = client.table('apple_workouts').select('id', count='exact', head=True).execute()
        return int(response.count or 0), None
    except Exception as exc:
        return 0, str(exc)


def get_apple_workout_types_present() -> Tuple[List[str], Optional[str]]:
    client, err = connect_supabase()
    if err:
        return [], str(err)
    try:
        response = client.table('apple_workouts').select('workout_type').order('workout_type', desc=False).execute()
        rows = list(response.data or [])
        values = sorted({
            _to_text(row.get('workout_type', '')).strip() or 'Other'
            for row in rows
        })
        return values, None
    except Exception as exc:
        return [], str(exc)


def get_apple_workout_day_aggregate(
    date_from: Any = None,
    date_to: Any = None,
    workout_type: Optional[str] = None,
) -> Tuple[pd.DataFrame, Optional[str]]:
    rows, _, err = get_apple_workouts(
        date_from=date_from,
        date_to=date_to,
        workout_type=workout_type,
        limit=200,
        offset=0,
    )
    if err:
        return pd.DataFrame(columns=['day', 'workouts', 'minutes', 'dominant_workout_type']), err
    if not rows:
        return pd.DataFrame(columns=['day', 'workouts', 'minutes', 'dominant_workout_type']), None

    all_rows = list(rows)
    while True:
        if len(rows) < 200:
            break
        rows, _, page_err = get_apple_workouts(
            date_from=date_from,
            date_to=date_to,
            workout_type=workout_type,
            limit=200,
            offset=len(all_rows),
        )
        if page_err:
            break
        all_rows.extend(rows)
        if not rows:
            break

    df = pd.DataFrame(all_rows)
    if df.empty:
        return pd.DataFrame(columns=['day', 'workouts', 'minutes', 'dominant_workout_type']), None

    df['start_time'] = pd.to_datetime(df.get('start_time'), errors='coerce', utc=True)
    df = df.dropna(subset=['start_time'])
    if df.empty:
        return pd.DataFrame(columns=['day', 'workouts', 'minutes', 'dominant_workout_type']), None

    df['day'] = df['start_time'].dt.date.astype(str)
    df['duration_minutes'] = pd.to_numeric(df.get('duration_minutes', 0), errors='coerce').fillna(0)

    grouped = df.groupby('day', as_index=False).agg(
        workouts=('apple_workout_key', 'count'),
        minutes=('duration_minutes', 'sum'),
    )
    dominant = (
        df.groupby(['day', 'workout_type'], as_index=False)
        .size()
        .sort_values(['day', 'size'], ascending=[True, False])
        .drop_duplicates(subset=['day'])
        .rename(columns={'workout_type': 'dominant_workout_type'})
    )
    merged = grouped.merge(dominant[['day', 'dominant_workout_type']], on='day', how='left')
    return merged.sort_values('day'), None


def get_apple_daily_for_date(target_date: Any) -> Tuple[pd.DataFrame, Optional[str]]:
    parsed = pd.to_datetime(target_date, errors='coerce')
    if pd.isna(parsed):
        return pd.DataFrame(columns=APPLE_ACTIVITY_COLUMNS), 'Invalid target date.'

    client, err = connect_supabase()
    if err:
        return pd.DataFrame(columns=APPLE_ACTIVITY_COLUMNS), str(err)

    day = parsed.date().isoformat()
    try:
        response = client.table('apple_activity_daily').select('*').eq('activity_date', day).order('activity_date', desc=False).execute()
        return pd.DataFrame(response.data or [], columns=APPLE_ACTIVITY_COLUMNS), None
    except Exception as exc:
        return pd.DataFrame(columns=APPLE_ACTIVITY_COLUMNS), str(exc)


def get_recent_apple_activity(days: int = 28) -> Tuple[pd.DataFrame, Optional[str]]:
    client, err = connect_supabase()
    if err:
        return pd.DataFrame(columns=APPLE_ACTIVITY_COLUMNS), str(err)

    cutoff = (date.today() - timedelta(days=max(1, int(days)) - 1)).isoformat()
    try:
        response = client.table('apple_activity_daily').select('*').gte('activity_date', cutoff).order('activity_date', desc=False).execute()
        return pd.DataFrame(response.data or [], columns=APPLE_ACTIVITY_COLUMNS), None
    except Exception as exc:
        return pd.DataFrame(columns=APPLE_ACTIVITY_COLUMNS), str(exc)


def get_recent_apple_workouts(days: int = 28) -> Tuple[pd.DataFrame, Optional[str]]:
    client, err = connect_supabase()
    if err:
        return pd.DataFrame(columns=APPLE_WORKOUT_COLUMNS), str(err)

    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)) - 1)).isoformat()
    try:
        response = client.table('apple_workouts').select('*').gte('start_time', cutoff_ts).order('start_time', desc=False).execute()
        return pd.DataFrame(response.data or [], columns=APPLE_WORKOUT_COLUMNS), None
    except Exception as exc:
        return pd.DataFrame(columns=APPLE_WORKOUT_COLUMNS), str(exc)


def save_daily_readiness_result(readiness_result: Dict[str, Any], readiness_date: Any) -> Dict[str, Any]:
    parsed = pd.to_datetime(readiness_date, errors='coerce')
    if pd.isna(parsed):
        return {'ok': False, 'error': 'Invalid readiness date.'}

    client, err = connect_supabase()
    if err:
        return {'ok': False, 'error': str(err)}

    target_day = parsed.date().isoformat()
    payload = {
        'readiness_date': target_day,
        'readiness_score': readiness_result.get('readiness_score'),
        'recovery_status': readiness_result.get('recovery_status'),
        'confidence_score': readiness_result.get('confidence_score'),
        'sleep_score': readiness_result.get('sleep_score'),
        'hrv_score': readiness_result.get('hrv_score'),
        'resting_hr_score': readiness_result.get('resting_hr_score'),
        'activity_load_score': readiness_result.get('activity_load_score'),
        'strength_load_score': readiness_result.get('strength_load_score'),
        'recovery_balance_score': readiness_result.get('recovery_balance_score'),
        'recommendation': readiness_result.get('recommendation'),
        'limiting_factors': readiness_result.get('limiting_factors'),
        'positive_factors': readiness_result.get('positive_factors'),
        'data_quality': readiness_result.get('data_quality'),
        'calculated_at': datetime.now(timezone.utc).isoformat(),
    }

    payload = _clean_payload(payload, DAILY_READINESS_COLUMNS)
    try:
        client.table('daily_readiness').upsert(payload, on_conflict='readiness_date').execute()
        return {'ok': True, 'error': None}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def get_daily_readiness_history(days: int = 60) -> Tuple[pd.DataFrame, Optional[str]]:
    client, err = connect_supabase()
    if err:
        return pd.DataFrame(columns=DAILY_READINESS_COLUMNS), str(err)

    cutoff = (date.today() - timedelta(days=max(1, int(days)) - 1)).isoformat()
    try:
        response = client.table('daily_readiness').select('*').gte('readiness_date', cutoff).order('readiness_date', desc=False).execute()
        return pd.DataFrame(response.data or [], columns=DAILY_READINESS_COLUMNS), None
    except Exception as exc:
        return pd.DataFrame(columns=DAILY_READINESS_COLUMNS), str(exc)


def get_import_summary() -> Dict[str, Any]:
    daily_df, daily_error = get_apple_activity_daily()
    workout_rows, total_workouts, workout_error = get_apple_workouts(limit=50, offset=0)
    workouts_df = pd.DataFrame(workout_rows or [], columns=APPLE_WORKOUT_COLUMNS)
    state = st.session_state.get(LAST_IMPORT_STATE_KEY, {}) if hasattr(st, 'session_state') else {}

    summary: Dict[str, Any] = {
        'connected': not daily_error and not workout_error,
        'daily_rows': int(len(daily_df)),
        'workout_rows': int(total_workouts or len(workouts_df)),
        'daily_error': daily_error,
        'workout_error': workout_error,
        'last_successful_import': '',
        'import_source': _to_text(state.get('import_source', 'Apple Health Export')).strip() or 'Apple Health Export',
        'date_range': 'No data',
        'current_activity_summary': {},
        'recent_workout': {},
        'weekly_workouts': 0,
        'records_added': int(state.get('daily_records_added', 0) or 0),
        'records_updated': int(state.get('daily_records_updated', 0) or 0),
        'duplicate_workouts_skipped': int(state.get('duplicate_workouts_skipped', 0) or 0),
        'import_errors': list(state.get('errors', []) or []),
    }

    if not daily_df.empty:
        daily_sorted = daily_df.copy()
        if 'activity_date' in daily_sorted.columns:
            daily_sorted['activity_date'] = pd.to_datetime(daily_sorted['activity_date'], errors='coerce', utc=True)
            daily_sorted = daily_sorted.dropna(subset=['activity_date']).sort_values('activity_date')
        if not daily_sorted.empty:
            summary['date_range'] = f"{daily_sorted['activity_date'].min().date().isoformat()} to {daily_sorted['activity_date'].max().date().isoformat()}"
            latest_row = daily_sorted.iloc[-1].to_dict()
            summary['current_activity_summary'] = latest_row
            imported_at = pd.to_datetime(daily_sorted.get('imported_at'), errors='coerce', utc=True) if 'imported_at' in daily_sorted.columns else pd.Series(dtype='datetime64[ns, UTC]')
            if not imported_at.empty and imported_at.notna().any():
                summary['last_successful_import'] = str(imported_at.max())
            else:
                summary['last_successful_import'] = _to_text(latest_row.get('imported_at', ''))

    if not workouts_df.empty:
        workout_sorted = workouts_df.copy()
        if 'start_time' in workout_sorted.columns:
            workout_sorted['start_time'] = pd.to_datetime(workout_sorted['start_time'], errors='coerce', utc=True)
            workout_sorted = workout_sorted.dropna(subset=['start_time']).sort_values('start_time')
        if not workout_sorted.empty:
            latest_workout = workout_sorted.iloc[-1].to_dict()
            summary['recent_workout'] = latest_workout
            recent_cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7)
            summary['weekly_workouts'] = int(workout_sorted[workout_sorted['start_time'] >= recent_cutoff].shape[0])
            imported_at = pd.to_datetime(workout_sorted.get('imported_at'), errors='coerce', utc=True) if 'imported_at' in workout_sorted.columns else pd.Series(dtype='datetime64[ns, UTC]')
            if not summary['last_successful_import'] and not imported_at.empty and imported_at.notna().any():
                summary['last_successful_import'] = str(imported_at.max())

    if state:
        summary.update({
            'last_successful_import': state.get('completed_at', summary['last_successful_import']),
            'import_source': state.get('import_source', summary['import_source']),
            'date_range': state.get('date_range', summary['date_range']),
            'records_added': int(state.get('daily_records_added', summary['records_added']) or summary['records_added']),
            'records_updated': int(state.get('daily_records_updated', summary['records_updated']) or summary['records_updated']),
            'duplicate_workouts_skipped': int(state.get('duplicate_workouts_skipped', summary['duplicate_workouts_skipped']) or summary['duplicate_workouts_skipped']),
            'import_errors': list(state.get('errors', summary['import_errors']) or summary['import_errors']),
        })

    return summary


def parse_apple_health_export(
    uploaded_file: Any,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    timeout_seconds: int = DEFAULT_IMPORT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    started_at = time.time()
    result = _init_import_state(uploaded_file)
    st.session_state[IMPORT_RUNNING_STATE_KEY] = True
    _commit_import_state(result, progress_callback)

    temp_zip_path: Optional[Path] = None

    def _check_timeout():
        elapsed = time.time() - started_at
        if elapsed > max(60, int(timeout_seconds)):
            raise TimeoutError(f'Apple Health import exceeded timeout of {int(timeout_seconds)} seconds.')

    try:
        if uploaded_file is None:
            raise ValueError('No file uploaded.')

        file_name = _to_text(getattr(uploaded_file, 'name', '')).strip().lower()
        if not (file_name.endswith('.zip') or file_name.endswith('.xml')):
            raise ValueError('Only .zip and .xml files are supported.')

        _update_import_state(result, progress_callback, stage='zip_uploading', status_message='Streaming upload to local temp file...')

        temp_zip_path = _stream_upload_to_named_temp(uploaded_file, callback=progress_callback, state=result)

        client, err = connect_supabase()
        if err:
            raise RuntimeError(str(err))

        rows_by_date: Dict[str, Dict[str, Any]] = {}
        avg_bucket: Dict[str, Dict[str, float]] = {}
        source_names: set[str] = set()
        date_min: Optional[str] = None
        date_max: Optional[str] = None
        workout_batch: List[Dict[str, Any]] = []

        def row_for(day: str) -> Dict[str, Any]:
            existing = rows_by_date.get(day)
            if existing is not None:
                return existing
            created = _new_daily_row(day)
            rows_by_date[day] = created
            return created

        if file_name.endswith('.zip'):
            with zipfile.ZipFile(str(temp_zip_path), 'r') as archive:
                _check_timeout()
                member = next((i for i in archive.infolist() if i.filename.lower().endswith('apple_health_export/export.xml') or i.filename.lower().endswith('/export.xml') or i.filename.lower() == 'export.xml'), None)
                if member is None:
                    raise FileNotFoundError('export.xml was not found inside ZIP. Expected apple_health_export/export.xml.')

                _update_import_state(
                    result,
                    progress_callback,
                    stage='export_xml_located',
                    status_message='export.xml located. Starting incremental parse...',
                    export_xml_size_bytes=int(member.file_size or 0),
                )

                with archive.open(member, 'r') as xml_stream:
                    for event, element in ET.iterparse(xml_stream, events=('end',)):
                        _check_timeout()
                        if event != 'end':
                            continue

                        tag = _local_name(element.tag)

                        if tag == 'Record':
                            result['records_processed'] = int(result.get('records_processed', 0)) + 1
                            result['records_seen'] = int(result.get('records_seen', 0)) + 1
                            attrs = element.attrib
                            record_type = _to_text(attrs.get('type', '')).strip()
                            if record_type not in SUPPORTED_RECORD_TYPES:
                                result['records_ignored'] = int(result.get('records_ignored', 0)) + 1
                                element.clear()
                                if result['records_processed'] % 5000 == 0:
                                    _update_import_state(result, progress_callback, stage='parsing_records', status_message='Parsing records incrementally...')
                                continue

                            activity_date = _parse_date(attrs.get('startDate') or attrs.get('endDate') or attrs.get('creationDate'))
                            if not activity_date:
                                result['records_ignored'] = int(result.get('records_ignored', 0)) + 1
                                element.clear()
                                continue

                            row = row_for(activity_date)
                            source_name = _to_text(attrs.get('sourceName', 'Apple Health')).strip()
                            if source_name:
                                source_names.add(source_name)

                            value = _to_float(attrs.get('value', 0), 0.0)
                            unit = _to_text(attrs.get('unit', ''))

                            if record_type == 'HKQuantityTypeIdentifierStepCount':
                                row['steps'] += value
                            elif record_type == 'HKQuantityTypeIdentifierActiveEnergyBurned':
                                row['active_energy_kcal'] += _parse_energy_kcal(value, unit)
                            elif record_type == 'HKQuantityTypeIdentifierBasalEnergyBurned':
                                row['basal_energy_kcal'] += _parse_energy_kcal(value, unit)
                            elif record_type == 'HKQuantityTypeIdentifierAppleExerciseTime':
                                row['exercise_minutes'] += _parse_minutes(value, unit)
                            elif record_type == 'HKQuantityTypeIdentifierAppleStandTime':
                                row['stand_hours'] += _parse_hours(value, unit)
                            elif record_type == 'HKQuantityTypeIdentifierDistanceWalkingRunning':
                                row['walking_running_distance_miles'] += _parse_distance_miles(value, unit)
                            elif record_type == 'HKQuantityTypeIdentifierFlightsClimbed':
                                row['flights_climbed'] += value
                            elif record_type == 'HKQuantityTypeIdentifierRestingHeartRate':
                                _add_avg_metric(avg_bucket, activity_date, 'resting_heart_rate', value)
                            elif record_type == 'HKQuantityTypeIdentifierWalkingHeartRateAverage':
                                _add_avg_metric(avg_bucket, activity_date, 'walking_heart_rate_average', value)
                            elif record_type == 'HKQuantityTypeIdentifierHeartRateVariabilitySDNN':
                                _add_avg_metric(avg_bucket, activity_date, 'heart_rate_variability_ms', value)
                            elif record_type == 'HKQuantityTypeIdentifierHeartRate':
                                _add_avg_metric(avg_bucket, activity_date, 'average_heart_rate', value)
                                row['maximum_heart_rate'] = max(float(row.get('maximum_heart_rate') or 0.0), float(value))
                            elif record_type == 'HKCategoryTypeIdentifierSleepAnalysis':
                                sleep_state = _to_text(attrs.get('value', '')).strip()
                                if _sleep_state_value(sleep_state):
                                    sleep_hours = _parse_duration_minutes(attrs.get('startDate'), attrs.get('endDate')) / 60.0
                                    if sleep_hours > 0:
                                        row['sleep_hours'] = round((row.get('sleep_hours') or 0.0) + sleep_hours, 2)

                            result['supported_records_found'] = int(result.get('supported_records_found', 0)) + 1

                            if date_min is None or activity_date < date_min:
                                date_min = activity_date
                            if date_max is None or activity_date > date_max:
                                date_max = activity_date

                            if result['records_processed'] % 5000 == 0:
                                _update_import_state(
                                    result,
                                    progress_callback,
                                    stage='parsing_records',
                                    status_message='Parsing records incrementally...',
                                    days_summarized=int(len(rows_by_date)),
                                    workouts_found=int(result.get('workouts_found', 0)),
                                )

                        elif tag == 'ActivitySummary':
                            attrs = element.attrib
                            summary_date = _parse_date(attrs.get('dateComponents') or attrs.get('startDate') or attrs.get('date') or attrs.get('endDate'))
                            if summary_date:
                                row = row_for(summary_date)
                                row['active_energy_kcal'] = _parse_energy_kcal(attrs.get('activeEnergyBurned') or attrs.get('activeEnergy'), attrs.get('energyUnit', attrs.get('unit', 'kcal')))
                                row['active_energy_goal_kcal'] = _parse_energy_kcal(attrs.get('activeEnergyBurnedGoal') or attrs.get('activeEnergyGoal'), attrs.get('energyUnit', attrs.get('unit', 'kcal')))
                                row['exercise_minutes'] = _parse_minutes(attrs.get('appleExerciseTime') or attrs.get('exerciseTime'), attrs.get('exerciseTimeUnit', attrs.get('unit', 'min')))
                                row['exercise_goal_minutes'] = _parse_minutes(attrs.get('appleExerciseTimeGoal') or attrs.get('exerciseTimeGoal'), attrs.get('exerciseTimeUnit', attrs.get('unit', 'min')))
                                row['stand_hours'] = _parse_hours(attrs.get('appleStandHours') or attrs.get('standHours'), attrs.get('standHoursUnit', attrs.get('unit', 'hr')))
                                row['stand_goal_hours'] = _parse_hours(attrs.get('appleStandHoursGoal') or attrs.get('standHoursGoal'), attrs.get('standHoursUnit', attrs.get('unit', 'hr')))
                                source_name = _to_text(attrs.get('sourceName', 'Apple Health')).strip()
                                if source_name:
                                    source_names.add(source_name)
                                if date_min is None or summary_date < date_min:
                                    date_min = summary_date
                                if date_max is None or summary_date > date_max:
                                    date_max = summary_date

                        elif tag == 'Workout':
                            attrs = element.attrib
                            start_time_raw = attrs.get('startDate')
                            end_time_raw = attrs.get('endDate')
                            workout = {
                                'workout_type': _normalize_workout_type(_to_text(attrs.get('workoutActivityType') or attrs.get('activityType') or attrs.get('type'), 'Other')),
                                'start_time': _parse_timestamp(start_time_raw),
                                'end_time': _parse_timestamp(end_time_raw),
                                'duration_minutes': _parse_duration_minutes(start_time_raw, end_time_raw),
                                'total_energy_kcal': _parse_energy_kcal(attrs.get('totalEnergyBurned'), attrs.get('totalEnergyBurnedUnit', 'kcal')),
                                'total_distance_miles': _parse_distance_miles(attrs.get('totalDistance'), attrs.get('totalDistanceUnit', 'mi')),
                                'average_heart_rate': _to_float(attrs.get('averageHeartRate', attrs.get('avgHeartRate')), 0.0) or None,
                                'maximum_heart_rate': _to_float(attrs.get('maximumHeartRate', attrs.get('maxHeartRate')), 0.0) or None,
                                'source_name': _to_text(attrs.get('sourceName', 'Apple Health')),
                                'source_version': _to_text(attrs.get('sourceVersion', '')),
                                'device': _to_text(attrs.get('device', '')),
                                'metadata': {
                                    'raw_workout_type': _to_text(attrs.get('workoutActivityType') or attrs.get('activityType') or attrs.get('type'), 'Other'),
                                    'duration_minutes': _parse_duration_minutes(start_time_raw, end_time_raw),
                                    'total_energy_unit': _to_text(attrs.get('totalEnergyBurnedUnit', 'kcal')),
                                    'total_distance_unit': _to_text(attrs.get('totalDistanceUnit', 'mi')),
                                },
                                'imported_at': datetime.now(timezone.utc).isoformat(),
                            }

                            for child in list(element):
                                if _local_name(child.tag) == 'MetadataEntry':
                                    m_key = _to_text(child.attrib.get('key', '')).strip()
                                    if m_key:
                                        workout['metadata'][m_key] = child.attrib.get('value')

                            workout['apple_workout_key'] = build_apple_workout_key({
                                'workout_type': workout.get('workout_type', 'Other'),
                                'start_time': start_time_raw,
                                'end_time': end_time_raw,
                                'source_name': workout.get('source_name', ''),
                                'device': workout.get('device', ''),
                            })
                            workout_batch.append(workout)
                            result['workouts_found'] = int(result.get('workouts_found', 0)) + 1

                            if len(workout_batch) >= SAVE_BATCH_SIZE:
                                saved = _save_workout_batch(client, workout_batch)
                                if not saved.get('ok'):
                                    raise RuntimeError(str((saved.get('errors') or [{'error': 'Unknown workout save error.'}])[0].get('error')))
                                result['workout_rows_saved'] = int(result.get('workout_rows_saved', 0)) + int(saved.get('saved', 0))
                                result['apple_workouts_added'] = int(result.get('apple_workouts_added', 0)) + int(saved.get('saved', 0))
                                workout_batch = []
                                _update_import_state(
                                    result,
                                    progress_callback,
                                    stage='saving_workouts',
                                    status_message='Saving Apple workout batch...',
                                )

                        element.clear()

        else:
            # XML input path: stream the XML file directly from uploaded content into temp,
            # then parse from disk.
            xml_path = Path(temp_zip_path)
            _update_import_state(
                result,
                progress_callback,
                stage='export_xml_located',
                status_message='XML located. Starting incremental parse...',
                export_xml_size_bytes=int(xml_path.stat().st_size) if xml_path.exists() else 0,
            )
            with open(xml_path, 'rb') as xml_stream:
                for event, element in ET.iterparse(xml_stream, events=('end',)):
                    _check_timeout()
                    if event != 'end':
                        continue
                    tag = _local_name(element.tag)
                    if tag == 'Record':
                        result['records_processed'] = int(result.get('records_processed', 0)) + 1
                    element.clear()

            # XML direct import is supported, but large user case is ZIP.
            raise RuntimeError('Direct XML upload is not supported for large imports. Please upload the Apple export ZIP.')

        if workout_batch:
            saved = _save_workout_batch(client, workout_batch)
            if not saved.get('ok'):
                raise RuntimeError(str((saved.get('errors') or [{'error': 'Unknown workout save error.'}])[0].get('error')))
            result['workout_rows_saved'] = int(result.get('workout_rows_saved', 0)) + int(saved.get('saved', 0))
            result['apple_workouts_added'] = int(result.get('apple_workouts_added', 0)) + int(saved.get('saved', 0))

        _apply_avg_metrics(rows_by_date, avg_bucket)

        if source_names:
            source_text = ', '.join(sorted(source_names)[:3])
            for row in rows_by_date.values():
                row['source'] = source_text

        all_daily_rows = sorted(rows_by_date.values(), key=lambda x: str(x.get('activity_date', '')))
        result['days_summarized'] = int(len(all_daily_rows))

        _update_import_state(result, progress_callback, stage='saving_daily', status_message='Saving daily summary batches...')
        for i in range(0, len(all_daily_rows), SAVE_BATCH_SIZE):
            _check_timeout()
            batch = all_daily_rows[i:i + SAVE_BATCH_SIZE]
            saved = _save_daily_activity_batch(client, batch)
            if not saved.get('ok'):
                raise RuntimeError(str((saved.get('errors') or [{'error': 'Unknown daily save error.'}])[0].get('error')))
            result['daily_rows_saved'] = int(result.get('daily_rows_saved', 0)) + int(saved.get('saved', 0))

            _update_import_state(
                result,
                progress_callback,
                stage='saving_daily',
                status_message='Saving daily summary batches...',
                daily_rows_saved=int(result.get('daily_rows_saved', 0)),
                workout_rows_saved=int(result.get('workout_rows_saved', 0)),
                days_summarized=int(result.get('days_summarized', 0)),
            )

        result['date_range'] = f'{date_min} to {date_max}' if date_min and date_max else 'No data'
        result['daily_records_added'] = int(result.get('daily_rows_saved', 0))
        result['daily_records_updated'] = 0
        result['duplicate_workouts_skipped'] = 0

        _update_import_state(
            result,
            progress_callback,
            stage='completed',
            status_message='Import completed successfully.',
            ok=True,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - started_at, 2),
            date_range=result.get('date_range', 'No data'),
        )
        return dict(result)

    except MemoryError as exc:
        _update_import_state(
            result,
            progress_callback,
            stage='error',
            status_message=f'MemoryError: {str(exc)}',
            ok=False,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - started_at, 2),
            errors=[{'error': f'MemoryError: {str(exc)}'}],
        )
        return dict(result)
    except zipfile.BadZipFile as exc:
        _update_import_state(
            result,
            progress_callback,
            stage='error',
            status_message=f'BadZipFile: {str(exc)}',
            ok=False,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - started_at, 2),
            errors=[{'error': f'BadZipFile: {str(exc)}'}],
        )
        return dict(result)
    except ET.ParseError as exc:
        _update_import_state(
            result,
            progress_callback,
            stage='error',
            status_message=f'Malformed XML: {str(exc)}',
            ok=False,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - started_at, 2),
            errors=[{'error': f'Malformed XML: {str(exc)}'}],
        )
        return dict(result)
    except TimeoutError as exc:
        _update_import_state(
            result,
            progress_callback,
            stage='error',
            status_message=f'Timeout: {str(exc)}',
            ok=False,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - started_at, 2),
            errors=[{'error': f'Timeout: {str(exc)}'}],
        )
        return dict(result)
    except Exception as exc:
        _update_import_state(
            result,
            progress_callback,
            stage='error',
            status_message=str(exc),
            ok=False,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - started_at, 2),
            errors=[{'error': str(exc)}],
        )
        return dict(result)
    finally:
        st.session_state[IMPORT_RUNNING_STATE_KEY] = False
        if temp_zip_path is not None:
            try:
                temp_zip_path.unlink(missing_ok=True)
            except Exception:
                pass