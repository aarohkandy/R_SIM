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
        self.assertEqual(components[2]["attachedToComponent"], components[1]["id"])
        self.assertEqual(components[3]["motorModel"], "Estes C6-5")

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
