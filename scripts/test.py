#!/usr/bin/env python3
"""Run repository regression tests and optionally emit JUnit with exact identities."""
import argparse
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append((test.id(), "passed", ""))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases.append((test.id(), "failure", self._exc_info_to_string(err, test)))

    def addError(self, test, err):
        super().addError(test, err)
        self.cases.append((test.id(), "error", self._exc_info_to_string(err, test)))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.cases.append((test.id(), "skipped", reason))

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.cases.append((test.id(), "skipped", "expected failure: " + self._exc_info_to_string(err, test)))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.cases.append((test.id(), "failure", "unexpected success"))

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.cases.append((subtest.id(), "failure", self._exc_info_to_string(err, test)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    if args.report:
        node = ET.Element("testsuite", tests=str(len(result.cases)), failures=str(sum(c[1] == "failure" for c in result.cases)), errors=str(sum(c[1] == "error" for c in result.cases)))
        for identity, status, detail in result.cases:
            classname, _, name = identity.rpartition(".")
            case = ET.SubElement(node, "testcase", classname=classname, name=name)
            if status != "passed":
                ET.SubElement(case, status, message=detail.splitlines()[-1] if detail else "").text = detail
        args.report.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(node).write(args.report, encoding="utf-8", xml_declaration=True)
    return int(not result.wasSuccessful() or result.testsRun == 0)


if __name__ == "__main__":
    sys.exit(main())
