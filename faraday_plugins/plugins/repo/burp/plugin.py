"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
import base64
import distutils.util  # pylint: disable=import-error
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Comment

from faraday_plugins.plugins.plugin import PluginXMLFormat
from faraday_plugins.plugins.plugins_utils import CVE_regex

__author__ = "Francisco Amato"
__copyright__ = "Copyright (c) 2013, Infobyte LLC"
__credits__ = ["Francisco Amato", "Micaela Ranea Sanchez"]
__license__ = ""
__version__ = "1.1.0"
__maintainer__ = "Francisco Amato"
__email__ = "famato@infobytesec.com"
__status__ = "Development"


class BurpXmlParser:
    """
    The objective of this class is to parse an xml file generated by the burp tool.

    TODO: Handle errors.
    TODO: Test burp output version. Handle what happens if the parser doesn't support it.
    TODO: Test cases.

    @param burp_xml_filepath A proper xml generated by burp
    """

    def __init__(self, xml_output):

        self.target = None
        self.port = "80"
        self.host = None

        tree = self.parse_xml(xml_output)
        if tree:
            self.items = [data for data in self.get_items(tree)]
        else:
            self.items = []

    def parse_xml(self, xml_output):
        """
        Open and parse an xml file.

        TODO: Write custom parser to just read the nodes that we need instead of
        reading the whole file.

        @return xml_tree An xml tree instance. None if error.
        """
        try:
            tree = ET.fromstring(xml_output)
        except SyntaxError as err:
            print(f"SyntaxError: {err}. {xml_output}")
            return None

        return tree

    def get_items(self, tree):
        """
        @return items A list of Host instances
        """

        for node in tree.findall('issue'):
            yield Item(node)


def get_attrib_from_subnode(xml_node, subnode_xpath_expr, attrib_name):
    """
    Finds a subnode in the item node and the retrieves a value from it

    @return An attribute value
    """
    node = xml_node.find(subnode_xpath_expr)

    if node is not None:
        return node.get(attrib_name)

    return None


class Item:
    """
    An abstract representation of a Item
    @param item_node A item_node taken from an burp xml tree
    """

    def __init__(self, item_node):
        self.node = item_node

        name = item_node.findall('name')[0]
        host_node = item_node.findall('host')[0]
        path = item_node.findall('path')[0]
        location = item_node.findall('location')[0]
        severity = item_node.findall('severity')[0]
        external_id = item_node.findall('type')[0]
        request = self.decode_binary_node('./requestresponse/request')
        response = self.decode_binary_node('./requestresponse/response')

        detail = self.do_clean(item_node.findall('issueDetail'))
        remediation = self.do_clean(item_node.findall('remediationBackground'))
        background = self.do_clean(item_node.findall('issueBackground'))
        self.cve = []
        if background:
            cve = CVE_regex.search(background)
            if cve:
                self.cve = [cve.group()]

        self.url = host_node.text

        url_data = urlsplit(self.url)

        self.protocol = url_data.scheme
        self.host = url_data.hostname

        # Use the port in the URL if it is defined, or 80 or 443 by default
        self.port = url_data.port or (443 if url_data.scheme == "https"
                                      else 80)

        self.name = name.text
        self.location = location.text
        self.path = path.text

        self.ip = host_node.get('ip')
        self.url = self.node.get('url')
        self.severity = severity.text
        self.request = request
        self.response = response
        self.detail = detail
        self.remediation = remediation
        self.background = background
        self.external_id = external_id.text

    @staticmethod
    def do_clean(value):

        myreturn = ""
        if value is not None:
            if len(value) > 0:
                myreturn = value[0].text
        return myreturn

    def decode_binary_node(self, path):
        """
        Finds a subnode matching `path` and returns its inner text if
        it has no base64 attribute or its base64 decoded inner text if
        it has it.
        """
        nodes = self.node.findall(path)
        try:
            subnode = nodes[0]
        except IndexError:
            return ""
        encoded = distutils.util.strtobool(subnode.get('base64', 'false'))
        if encoded:
            res = base64.b64decode(subnode.text).decode('utf-8', errors="backslashreplace")
        else:
            res = subnode.text
        return "".join([ch for ch in res if ord(ch) <= 128])

    def get_text_from_subnode(self, subnode_xpath_expr):
        """
        Finds a subnode in the host node and the retrieves a value from it.
        @return An attribute value
        """

        sub_node = self.node.find(subnode_xpath_expr)
        if sub_node is not None:
            return sub_node.text

        return None


class BurpPlugin(PluginXMLFormat):
    """
    Example plugin to parse burp output.
    """

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.identifier_tag = "issues"
        self.id = "Burp"
        self.name = "Burp XML Output Plugin"
        self.plugin_version = "0.0.2"
        self.version = "1.6.05 BurpPro"
        self.framework_version = "1.0.0"
        self.options = None
        self._current_output = None
        self.target = None

    def parseOutputString(self, output):

        parser = BurpXmlParser(output)
        for item in parser.items:

            h_id = self.createAndAddHost(item.ip, hostnames=[item.host])
            s_id = self.createAndAddServiceToHost(
                h_id,
                item.protocol,
                "tcp",
                ports=[str(item.port)],
                status="open")

            if item.background:
                desc = item.background
            else:
                desc = ""
            desc = self.removeHtml(desc)
            data = ""
            if item.detail:
                desc += self.removeHtml(item.detail)
                data = self.removeHtml(item.detail)
            resolution = self.removeHtml(item.remediation) if item.remediation else ""

            self.createAndAddVulnWebToService(
                h_id,
                s_id,
                item.name,
                desc=desc,
                data=data,
                severity=item.severity,
                website=item.host,
                path=item.path,
                request=item.request,
                response=item.response,
                resolution=resolution,
                external_id=item.external_id,
                cve=item.cve
            )

        del parser

    def removeHtml(self, markup):
        soup = BeautifulSoup(markup, "html.parser")

        # Replace line breaks and paragraphs for new lines
        for tag in soup.find_all(["br", "p"]):
            tag.append("\n")
            tag.unwrap()

        # Replace lists for * and new lines
        for tag in soup.find_all(["ul", "ol"]):
            for item in tag.find_all("li"):
                item.insert_before("* ")
                item.append("\n")
                item.unwrap()
            tag.unwrap()

        # Remove all other HTML tags
        for tag in soup.find_all():
            tag.unwrap()

        # Remove all comments
        for child in soup.children:
            if isinstance(child, Comment):
                child.extract()

        return str(soup)


def createPlugin(ignore_info=False):
    return BurpPlugin(ignore_info=ignore_info)
