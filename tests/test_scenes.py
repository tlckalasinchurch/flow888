from flow8.service import ALL_CHANNELS, Flow8Service


def test_scene_capture_recall_restores_all_mixer_parameters_without_phantom():
    service = Flow8Service()
    service.set_parameter(0, "phantom_power", True)
    for channel in range(7):
        service.set_parameter(channel, "fader", channel * 10)
        service.set_parameter(channel, "pan", channel - 3)
        service.set_parameter(channel, "mute", channel % 2 == 0)
    service.set_parameter("main_l", "fader", 90)
    service.set_parameter("main_l", "mute", True)
    service.set_parameter("main_r", "fader", 88)
    service.set_parameter("main_r", "mute", False)
    service.save_scene("Worship Start")

    for channel in ALL_CHANNELS:
        service.set_parameter(channel, "fader", -99)
        service.set_parameter(channel, "mute", False)
        if isinstance(channel, int):
            service.set_parameter(channel, "pan", 99)
    service.set_parameter(0, "phantom_power", False)
    service.recall_scene("Worship Start")

    for channel in range(7):
        assert service.state[channel] == {
            "fader": channel * 10,
            "pan": channel - 3,
            "mute": channel % 2 == 0,
        }
    assert service.state["main_l"] == {"fader": 90, "mute": True}
    assert service.state["main_r"] == {"fader": 88, "mute": False}
    assert service.phantom_power[0] is False
    assert "PHANTOM POWER UNCHANGED" in service.status_message


def test_scene_manager_limits_to_eight_and_excludes_unknown_parameters():
    service = Flow8Service()
    for index in range(9):
        service.save_scene(f"Scene {index}")
    assert len(service.scenes.list_snapshots()) == 8
    assert "Scene 0" not in service.scenes.names()
    snapshot = service.scenes.get("Scene 8")
    assert all("phantom_power" not in values for values in snapshot.parameters.values())
