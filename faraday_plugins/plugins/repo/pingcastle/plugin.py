#!/usr/bin/env python
"""
Faraday Penetration Test IDE
Copyright (C) 2016  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information
"""
import xml.etree.ElementTree as ET
from datetime import datetime

from faraday_plugins.plugins.plugin import PluginXMLFormat

__author__ = 'Gonzalo Martinez'
__copyright__ = 'Copyright 2023, Faraday Project'
__credits__ = ['Gonzalo Martinez']
__license__ = ''
__version__ = '1.0.0'
__status__ = 'Development'


class AppSpiderParser:
    def __init__(self, xml_output):
        self.tree = self.parse_xml(xml_output)
        if self.tree:
            self.vuln_list = self.tree.find('VulnList')
            self.name_scan = self.tree.findtext('ScanName')
        else:
            self.tree = None

    @staticmethod
    def parse_xml(xml_output):
        try:
            tree = ET.fromstring(xml_output)
        except SyntaxError as err:
            print(f'SyntaxError In xml: {err}. {xml_output}')
            return None
        return tree


class PingCastlePlugin(PluginXMLFormat):

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.identifier_tag = ["HealthcheckData"]
        self.id = 'PingCastle'
        self.name = 'Ping Castle XML Output Plugin'
        self.plugin_version = '1.0.0'
        self.version = '1.0.0'
        self.framework_version = '1.0.0'

    @staticmethod
    def map_severity(score):
        if score == 0:
            return "low"
        elif score < 11:
            return "medium"
        elif score < 31:
            return "high"
        elif score > 30:
            return "critical"

    def parseOutputString(self, output):
        tree = ET.fromstring(output)
        url = tree.find("DomainFQDN").text

        host_id = self.createAndAddHost(name=url)
        for risk in tree.find("RiskRules"):
            vuln = {}
            vuln["severity"] = self.map_severity(int(risk.find("Points").text))
            name = risk.find("Rationale").text
            vuln["name"] = risk.find('Model').text
            desc = ""
            desc += f"Category: {risk.find('Category').text}\n"
            desc += f"Model: {risk.find('Model').text}\n"
            desc += f"RiskId: {risk.find('RiskId').text}\n"
            desc += f"Rationale: {risk.find('Rationale').text}"
            vuln["desc"] = desc
            self.createAndAddVulnToHost(host_id=host_id, **vuln)


def createPlugin(*args, **kwargs):
    return PingCastlePlugin(*args, **kwargs)
