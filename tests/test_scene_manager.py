from flow8.scenes import SceneManager


def test_scene_manager_captures_only_safe_parameters_and_is_bounded():
    manager = SceneManager(max_snapshots=2)
    state = {1: {"fader": 64, "pan": 0, "mute": False, "phantom_power": True}}
    manager.save_snapshot("A", state)
    manager.save_snapshot("B", state)
    manager.save_snapshot("C", state)
    assert manager.names() == ("B", "C")
    assert "phantom_power" not in manager.get("C").parameters[1]


def test_scene_manager_loads_a_deep_copy():
    loaded = []
    manager = SceneManager(state_loader=loaded.append)
    manager.save_snapshot("Speech", {1: {"fader": 55, "pan": -10, "mute": False}})
    manager.load_snapshot("Speech")
    loaded[0][1]["fader"] = 0
    assert manager.get("Speech").parameters[1]["fader"] == 55
