# RESD / Sensor Streams

This directory is reserved for deterministic sensor-stream artifacts used by Backend B.

The first Backend-B implementation uses the Renode External Control API payload shape in
`rocketsim.control.backend_renode.sensor_packet_to_injection_frame`. If later bring-up
uses Renode RESD files instead, generate them here from the same plant telemetry so the
runtime source remains the simulation state, not hand-authored fixtures.
