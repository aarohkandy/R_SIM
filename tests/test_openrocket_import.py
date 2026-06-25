import io
import sys
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from f_backend import app  # noqa: E402
from openrocket_import import parse_openrocket_design  # noqa: E402


SAMPLE_OPENROCKET_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<openrocket>
  <rocket>
    <name>Imported Active Test Rocket</name>
    <subcomponents>
      <stage>
        <subcomponents>
          <nosecone>
            <name>Ogive Nose</name>
            <length>0.120</length>
            <aftRadius>0.020</aftRadius>
            <mass>0.035</mass>
          </nosecone>
          <bodytube>
            <name>Main Body</name>
            <length>0.560</length>
            <outerRadius>0.020</outerRadius>
            <mass>0.135</mass>
            <subcomponents>
              <trapezoidfinset>
                <name>Three Active Fins</name>
                <finCount>3</finCount>
                <rootChord>0.090</rootChord>
                <tipChord>0.045</tipChord>
                <height>0.055</height>
                <thickness>0.003</thickness>
                <sweep>0.020</sweep>
                <mass>0.045</mass>
              </trapezoidfinset>
              <motor>
                <manufacturer>Estes</manufacturer>
                <designation>Estes C6-5</designation>
                <diameter>0.018</diameter>
                <length>0.070</length>
                <burnTime>1.600</burnTime>
                <totalImpulse>10.000</totalImpulse>
                <averageThrust>6.000</averageThrust>
                <mass>0.017</mass>
              </motor>
            </subcomponents>
          </bodytube>
        </subcomponents>
      </stage>
    </subcomponents>
  </rocket>
</openrocket>
"""


class OpenRocketImportTests(unittest.TestCase):
    def test_parse_plain_openrocket_xml(self):
        imported = parse_openrocket_design(SAMPLE_OPENROCKET_XML, "active-test.ork")
        rocket = imported.rocket_data
        components = rocket["components"]

        self.assertEqual(imported.design_name, "Imported Active Test Rocket")
        self.assertEqual([component["type"] for component in components], ["Nose Cone", "Body Tube", "Fins", "Motor"])
        self.assertAlmostEqual(rocket["totalHeight"], 680.0)
        self.assertAlmostEqual(rocket["weight"], 232.0)
        self.assertAlmostEqual(rocket["cg"], 319.6)
        self.assertEqual(components[2]["finCount"], 3)
        self.assertEqual(components[2]["finShape"], "trapezoidal")
        self.assertAlmostEqual(components[2]["finTipChord"], 45.0)
        self.assertAlmostEqual(components[2]["finThickness"], 3.0)
        self.assertAlmostEqual(components[2]["finSweep"], 20.0)
        self.assertEqual(components[2]["attachedToComponent"], components[1]["id"])
        self.assertEqual(components[3]["motorModel"], "Estes C6-5")

    def test_parse_openrocket_rich_fin_geometry(self):
        xml = SAMPLE_OPENROCKET_XML.replace(
            b"<trapezoidfinset>",
            (
                b"<ellipticalfinset><name>Elliptical Canted Fins</name><finCount>4</finCount>"
                b"<rootChord>0.110</rootChord><tipChord>0.035</tipChord><height>0.065</height>"
                b"<thickness>0.004</thickness><sweep>0.018</sweep><tabLength>0.045</tabLength>"
                b"<tabHeight>0.016</tabHeight><cantAngle>2.5</cantAngle><crossSection>airfoil</crossSection>"
                b"<mass>0.052</mass></ellipticalfinset><trapezoidfinset>"
            ),
        )
        imported = parse_openrocket_design(xml, "rich-fins.ork")
        fins = next(component for component in imported.rocket_data["components"] if component["name"] == "Elliptical Canted Fins")

        self.assertEqual(fins["finShape"], "elliptical")
        self.assertEqual(fins["finCount"], 4)
        self.assertAlmostEqual(fins["finWidth"], 110.0)
        self.assertAlmostEqual(fins["finTipChord"], 35.0)
        self.assertAlmostEqual(fins["finHeight"], 65.0)
        self.assertAlmostEqual(fins["finThickness"], 4.0)
        self.assertAlmostEqual(fins["finSweep"], 18.0)
        self.assertAlmostEqual(fins["finTabLength"], 45.0)
        self.assertAlmostEqual(fins["finTabHeight"], 16.0)
        self.assertAlmostEqual(fins["finCantAngle"], 2.5)
        self.assertEqual(fins["finCrossSection"], "airfoil")

    def test_parse_zipped_ork_archive(self):
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("rocket.ork", SAMPLE_OPENROCKET_XML)

        imported = parse_openrocket_design(archive_bytes.getvalue(), "archive.ork")

        self.assertEqual(imported.design_name, "Imported Active Test Rocket")
        self.assertEqual(len(imported.rocket_data["components"]), 4)

    def test_import_endpoint_returns_rocket_data_and_enriched_motor_curve(self):
        client = app.test_client()
        response = client.post(
            "/api/openrocket/import",
            data={"file": (io.BytesIO(SAMPLE_OPENROCKET_XML), "active-test.ork")},
            content_type="multipart/form-data",
        )
        body = response.get_json()
        motor = next(component for component in body["rocketData"]["components"] if component["type"] == "Motor")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["success"])
        self.assertEqual(body["source"], "openrocket_import")
        self.assertEqual(body["rocketData"]["totalHeight"], 680.0)
        self.assertEqual(motor["motorModel"], "Estes C6-5")
        self.assertGreater(len(motor["thrustCurve"]), 5)

    def test_parse_openrocket_mass_component(self):
        xml = SAMPLE_OPENROCKET_XML.replace(
            b"<trapezoidfinset>",
            b"<masscomponent><name>Tracker Battery</name><mass>0.065</mass><position>0.240</position><role>battery</role></masscomponent><trapezoidfinset>",
        )
        imported = parse_openrocket_design(xml, "mass-component.ork")
        mass_component = next(component for component in imported.rocket_data["components"] if component["type"] == "Mass Component")
        body = next(component for component in imported.rocket_data["components"] if component["type"] == "Body Tube")

        self.assertEqual(mass_component["name"], "Tracker Battery")
        self.assertAlmostEqual(mass_component["weight"], 65.0)
        self.assertAlmostEqual(mass_component["axialPosition"], 240.0)
        self.assertEqual(mass_component["massRole"], "battery")
        self.assertEqual(mass_component["attachedToComponent"], body["id"])

    def test_parse_openrocket_parachute_component(self):
        xml = SAMPLE_OPENROCKET_XML.replace(
            b"<trapezoidfinset>",
            b"<parachute><name>Main Parachute</name><mass>0.038</mass><diameter>0.550</diameter><cd>1.60</cd><deployAltitude>0.120</deployAltitude></parachute><trapezoidfinset>",
        )
        imported = parse_openrocket_design(xml, "recovery.ork")
        parachute = next(component for component in imported.rocket_data["components"] if component["type"] == "Parachute")
        body = next(component for component in imported.rocket_data["components"] if component["type"] == "Body Tube")

        self.assertEqual(parachute["name"], "Main Parachute")
        self.assertEqual(parachute["recoveryRole"], "main")
        self.assertEqual(parachute["deployEvent"], "altitude")
        self.assertAlmostEqual(parachute["deployAltitude"], 120.0)
        self.assertAlmostEqual(parachute["dragCoefficient"], 1.6)
        self.assertGreater(parachute["dragArea"], 0.2)
        self.assertEqual(parachute["attachedToComponent"], body["id"])

    def test_parse_openrocket_streamer_component(self):
        xml = SAMPLE_OPENROCKET_XML.replace(
            b"<trapezoidfinset>",
            b"<streamer><name>Drogue Streamer</name><mass>0.016</mass><stripLength>1.200</stripLength><stripWidth>0.080</stripWidth><cd>1.05</cd><deployEvent>apogee</deployEvent></streamer><trapezoidfinset>",
        )
        imported = parse_openrocket_design(xml, "streamer.ork")
        streamer = next(component for component in imported.rocket_data["components"] if component["type"] == "Streamer")
        body = next(component for component in imported.rocket_data["components"] if component["type"] == "Body Tube")

        self.assertEqual(streamer["name"], "Drogue Streamer")
        self.assertEqual(streamer["recoveryRole"], "drogue")
        self.assertEqual(streamer["deployEvent"], "apogee")
        self.assertAlmostEqual(streamer["streamerLength"], 1.2)
        self.assertAlmostEqual(streamer["streamerWidth"], 0.08)
        self.assertAlmostEqual(streamer["dragArea"], 0.096)
        self.assertAlmostEqual(streamer["dragCoefficient"], 1.05)
        self.assertEqual(streamer["attachedToComponent"], body["id"])

    def test_parse_openrocket_shock_cord_component(self):
        xml = SAMPLE_OPENROCKET_XML.replace(
            b"<trapezoidfinset>",
            b"<shockcord><name>Nylon Harness</name><mass>0.024</mass><length>3.000</length><diameter>0.003</diameter><maxTensionN>450</maxTensionN><material>nylon</material></shockcord><trapezoidfinset>",
        )
        imported = parse_openrocket_design(xml, "shock-cord.ork")
        shock_cord = next(component for component in imported.rocket_data["components"] if component["type"] == "Shock Cord")
        body = next(component for component in imported.rocket_data["components"] if component["type"] == "Body Tube")

        self.assertEqual(shock_cord["name"], "Nylon Harness")
        self.assertAlmostEqual(shock_cord["weight"], 24.0)
        self.assertAlmostEqual(shock_cord["cordLength"], 3.0)
        self.assertAlmostEqual(shock_cord["cordDiameter"], 3.0)
        self.assertAlmostEqual(shock_cord["maxTensionN"], 450.0)
        self.assertEqual(shock_cord["material"], "nylon")
        self.assertEqual(shock_cord["attachedToComponent"], body["id"])

    def test_parse_openrocket_motor_mount_hardware(self):
        xml = SAMPLE_OPENROCKET_XML.replace(
            b"<trapezoidfinset>",
            (
                b"<innertube><name>Motor Mount Tube</name><mass>0.036</mass><length>0.160</length>"
                b"<innerRadius>0.0145</innerRadius><outerRadius>0.017</outerRadius><material>phenolic</material></innertube>"
                b"<centeringring><name>Centering Rings</name><mass>0.018</mass><ringCount>2</ringCount>"
                b"<innerRadius>0.017</innerRadius><outerRadius>0.020</outerRadius><thickness>0.004</thickness>"
                b"<material>plywood</material></centeringring><trapezoidfinset>"
            ),
        )
        imported = parse_openrocket_design(xml, "motor-mount.ork")
        motor_mount = next(component for component in imported.rocket_data["components"] if component["type"] == "Motor Mount")
        centering_ring = next(component for component in imported.rocket_data["components"] if component["type"] == "Centering Ring")
        body = next(component for component in imported.rocket_data["components"] if component["type"] == "Body Tube")

        self.assertEqual(motor_mount["name"], "Motor Mount Tube")
        self.assertAlmostEqual(motor_mount["weight"], 36.0)
        self.assertAlmostEqual(motor_mount["mountLength"], 160.0)
        self.assertAlmostEqual(motor_mount["innerDiameter"], 29.0)
        self.assertAlmostEqual(motor_mount["outerDiameter"], 34.0)
        self.assertEqual(motor_mount["material"], "phenolic")
        self.assertEqual(motor_mount["attachedToComponent"], body["id"])
        self.assertEqual(centering_ring["name"], "Centering Rings")
        self.assertAlmostEqual(centering_ring["weight"], 18.0)
        self.assertEqual(centering_ring["ringCount"], 2)
        self.assertAlmostEqual(centering_ring["innerDiameter"], 34.0)
        self.assertAlmostEqual(centering_ring["outerDiameter"], 40.0)
        self.assertAlmostEqual(centering_ring["thickness"], 4.0)
        self.assertEqual(centering_ring["material"], "plywood")
        self.assertEqual(centering_ring["attachedToComponent"], body["id"])
        self.assertAlmostEqual(imported.rocket_data["totalHeight"], 680.0)

    def test_parse_openrocket_airframe_internal_hardware(self):
        xml = SAMPLE_OPENROCKET_XML.replace(
            b"<trapezoidfinset>",
            (
                b"<tubeCoupler><name>Payload Coupler</name><mass>0.028</mass><length>0.084</length>"
                b"<innerRadius>0.024</innerRadius><outerRadius>0.026</outerRadius><material>phenolic</material></tubeCoupler>"
                b"<bulkhead><name>Avionics Bulkhead</name><mass>0.022</mass><outerRadius>0.020</outerRadius>"
                b"<thickness>0.005</thickness><material>plywood</material></bulkhead><trapezoidfinset>"
            ),
        )
        imported = parse_openrocket_design(xml, "internal-airframe.ork")
        coupler = next(component for component in imported.rocket_data["components"] if component["type"] == "Tube Coupler")
        bulkhead = next(component for component in imported.rocket_data["components"] if component["type"] == "Bulkhead")
        body = next(component for component in imported.rocket_data["components"] if component["type"] == "Body Tube")

        self.assertEqual(coupler["name"], "Payload Coupler")
        self.assertAlmostEqual(coupler["weight"], 28.0)
        self.assertAlmostEqual(coupler["couplerLength"], 84.0)
        self.assertAlmostEqual(coupler["innerDiameter"], 48.0)
        self.assertAlmostEqual(coupler["outerDiameter"], 52.0)
        self.assertEqual(coupler["material"], "phenolic")
        self.assertEqual(coupler["attachedToComponent"], body["id"])
        self.assertEqual(bulkhead["name"], "Avionics Bulkhead")
        self.assertAlmostEqual(bulkhead["weight"], 22.0)
        self.assertAlmostEqual(bulkhead["outerDiameter"], 40.0)
        self.assertAlmostEqual(bulkhead["thickness"], 5.0)
        self.assertEqual(bulkhead["material"], "plywood")
        self.assertEqual(bulkhead["attachedToComponent"], body["id"])
        self.assertAlmostEqual(imported.rocket_data["totalHeight"], 680.0)

    def test_parse_openrocket_launch_hardware(self):
        xml = SAMPLE_OPENROCKET_XML.replace(
            b"<trapezoidfinset>",
            (
                b"<launchlug><name>Quarter-inch Lug</name><mass>0.010</mass><length>0.045</length>"
                b"<innerRadius>0.0025</innerRadius><outerRadius>0.004</outerRadius><standoffHeight>0.003</standoffHeight>"
                b"<position>0.280</position><material>phenolic</material></launchlug>"
                b"<railbutton><name>1010 Rail Buttons</name><mass>0.008</mass><diameter>0.010</diameter>"
                b"<height>0.012</height><instanceCount>2</instanceCount><buttonSpacing>0.170</buttonSpacing>"
                b"<standoffHeight>0.004</standoffHeight><position>0.420</position><material>nylon</material></railbutton>"
                b"<trapezoidfinset>"
            ),
        )
        imported = parse_openrocket_design(xml, "launch-hardware.ork")
        launch_lug = next(component for component in imported.rocket_data["components"] if component["type"] == "Launch Lug")
        rail_button = next(component for component in imported.rocket_data["components"] if component["type"] == "Rail Button")
        body = next(component for component in imported.rocket_data["components"] if component["type"] == "Body Tube")

        self.assertEqual(launch_lug["name"], "Quarter-inch Lug")
        self.assertAlmostEqual(launch_lug["weight"], 10.0)
        self.assertAlmostEqual(launch_lug["length"], 45.0)
        self.assertAlmostEqual(launch_lug["diameter"], 8.0)
        self.assertAlmostEqual(launch_lug["innerDiameter"], 5.0)
        self.assertAlmostEqual(launch_lug["standoffHeight"], 3.0)
        self.assertEqual(launch_lug["material"], "phenolic")
        self.assertEqual(launch_lug["attachedToComponent"], body["id"])
        self.assertEqual(rail_button["name"], "1010 Rail Buttons")
        self.assertAlmostEqual(rail_button["weight"], 8.0)
        self.assertAlmostEqual(rail_button["length"], 12.0)
        self.assertAlmostEqual(rail_button["diameter"], 10.0)
        self.assertEqual(rail_button["instanceCount"], 2)
        self.assertAlmostEqual(rail_button["buttonSpacing"], 170.0)
        self.assertAlmostEqual(rail_button["standoffHeight"], 4.0)
        self.assertEqual(rail_button["material"], "nylon")
        self.assertEqual(rail_button["attachedToComponent"], body["id"])
        self.assertAlmostEqual(imported.rocket_data["totalHeight"], 680.0)

    def test_import_endpoint_rejects_non_openrocket_extension(self):
        client = app.test_client()
        response = client.post(
            "/api/openrocket/import",
            data={"file": (io.BytesIO(b"not xml"), "rocket.txt")},
            content_type="multipart/form-data",
        )
        body = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(body["success"])
        self.assertIn("Only .ork or .xml", body["message"])


if __name__ == "__main__":
    unittest.main()
