#!/usr/bin/env python
import sys
print("Python path:", sys.executable)

try:
    from components.workout_command_center import workout_command_center
    print("✓ workout_command_center imported successfully")
except Exception as e:
    print(f"✗ Error importing workout_command_center: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from components.exercise_intelligence_panel import exercise_intelligence_panel
    print("✓ exercise_intelligence_panel imported successfully")
except Exception as e:
    print(f"✗ Error importing exercise_intelligence_panel: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from engines.exercise_intelligence import ExerciseIntelligence
    print("✓ ExerciseIntelligence imported successfully")
except Exception as e:
    print(f"✗ Error importing ExerciseIntelligence: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test that function signature matches
import inspect
sig = inspect.signature(workout_command_center)
print(f"\nworkout_command_center signature: {sig}")
print(f"Parameters: {list(sig.parameters.keys())}")

if 'exercise_data' in sig.parameters:
    print("✓ exercise_data parameter is present in function signature")
else:
    print("✗ exercise_data parameter is MISSING from function signature")
    sys.exit(1)

print("\n✓✓✓ All imports and signature checks passed!")
