from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple
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

LAST_IMPORT_STATE_KEY = 'apple_health_last_import_result'

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


def get_apple_workouts() -> Tuple[pd.DataFrame, Optional[str]]:
    client, err = connect_supabase()
    if err:
        return pd.DataFrame(columns=APPLE_WORKOUT_COLUMNS), str(err)

    try:
        response = client.table('apple_workouts').select('*').order('start_time', desc=False).execute()
        return pd.DataFrame(response.data or [], columns=APPLE_WORKOUT_COLUMNS), None
    except Exception as exc:
        return pd.DataFrame(columns=APPLE_WORKOUT_COLUMNS), str(exc)


def get_import_summary() -> Dict[str, Any]:
    daily_df, daily_error = get_apple_activity_daily()
    workouts_df, workout_error = get_apple_workouts()
    state = st.session_state.get(LAST_IMPORT_STATE_KEY, {}) if hasattr(st, 'session_state') else {}

    summary: Dict[str, Any] = {
        'connected': not daily_error and not workout_error,
        'daily_rows': int(len(daily_df)),
        'workout_rows': int(len(workouts_df)),
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
            daily_sorted['activity_date'] = pd.to_datetime(daily_sorted['activity_date'], errors='coerce')
            daily_sorted = daily_sorted.dropna(subset=['activity_date']).sort_values('activity_date')
        if not daily_sorted.empty:
            summary['date_range'] = f"{daily_sorted['activity_date'].min().date().isoformat()} to {daily_sorted['activity_date'].max().date().isoformat()}"
            latest_row = daily_sorted.iloc[-1].to_dict()
            summary['current_activity_summary'] = latest_row
            imported_at = pd.to_datetime(daily_sorted.get('imported_at'), errors='coerce') if 'imported_at' in daily_sorted.columns else pd.Series(dtype='datetime64[ns]')
            if not imported_at.empty and imported_at.notna().any():
                summary['last_successful_import'] = str(imported_at.max())
            else:
                summary['last_successful_import'] = _to_text(latest_row.get('imported_at', ''))

    if not workouts_df.empty:
        workout_sorted = workouts_df.copy()
        if 'start_time' in workout_sorted.columns:
            workout_sorted['start_time'] = pd.to_datetime(workout_sorted['start_time'], errors='coerce')
            workout_sorted = workout_sorted.dropna(subset=['start_time']).sort_values('start_time')
        if not workout_sorted.empty:
            latest_workout = workout_sorted.iloc[-1].to_dict()
            summary['recent_workout'] = latest_workout
            recent_cutoff = pd.Timestamp.now() - pd.Timedelta(days=7)
            summary['weekly_workouts'] = int(workout_sorted[workout_sorted['start_time'] >= recent_cutoff].shape[0])
            imported_at = pd.to_datetime(workout_sorted.get('imported_at'), errors='coerce') if 'imported_at' in workout_sorted.columns else pd.Series(dtype='datetime64[ns]')
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


def parse_apple_health_export(uploaded_file: Any) -> Dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    xml_path, error = extract_export_xml(uploaded_file)
    if error or xml_path is None:
        result = {
            'ok': False,
            'import_source': _to_text(getattr(uploaded_file, 'name', 'Apple Health Export')).strip() or 'Apple Health Export',
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'duration_seconds': 0.0,
            'date_range': 'No data',
            'records_seen': 0,
            'records_ignored': 0,
            'daily_records_added': 0,
            'daily_records_updated': 0,
            'apple_workouts_added': 0,
            'duplicate_workouts_skipped': 0,
            'errors': [{'error': error or 'Unable to extract export.xml.'}],
        }
        st.session_state[LAST_IMPORT_STATE_KEY] = result
        return result

    try:
        daily_rows, stats = aggregate_daily_activity(parse_health_records(xml_path))
        workout_rows = list(parse_apple_workouts(xml_path))

        daily_result = save_daily_activity(daily_rows)
        workout_result = save_apple_workouts(workout_rows)

        errors: List[Dict[str, Any]] = []
        errors.extend(list(daily_result.get('errors', [])))
        errors.extend(list(workout_result.get('errors', [])))

        result = {
            'ok': not errors,
            'import_source': _to_text(getattr(uploaded_file, 'name', 'Apple Health Export')).strip() or 'Apple Health Export',
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'duration_seconds': round((datetime.now(timezone.utc) - started_at).total_seconds(), 2),
            'date_range': stats.get('date_range', 'No data'),
            'records_seen': int(stats.get('records_seen', 0)),
            'records_ignored': int(stats.get('records_ignored', 0)),
            'daily_records_added': int(daily_result.get('added', 0)),
            'daily_records_updated': int(daily_result.get('updated', 0)),
            'apple_workouts_added': int(workout_result.get('added', 0)),
            'duplicate_workouts_skipped': int(workout_result.get('duplicate_skipped', 0)),
            'errors': errors,
            'summary': stats,
            'daily_rows': daily_rows,
            'workout_rows': workout_rows,
        }
        st.session_state[LAST_IMPORT_STATE_KEY] = result
        return result
    finally:
        try:
            shutil.rmtree(xml_path.parent, ignore_errors=True)
        except Exception:
            pass