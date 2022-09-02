#!/usr/bin/python3
# coding=utf-8

from pathlib import Path
import click
import os
import sys
import subprocess

from xml.etree import ElementTree
from xml.etree.ElementTree import (Element, SubElement)
from pyocd.core.memory_map import MemoryType
from pyocd.target.pack.cmsis_pack import (CmsisPack)


class CommentedTreeBuilder(ElementTree.TreeBuilder):
    def comment(self, data):
        self.start(ElementTree.Comment, {})
        self.data(data)
        self.end(ElementTree.Comment)


def pretty_xml(element, indent, newline, level=0):
    if element:
        if (element.text is None) or element.text.isspace():
            element.text = newline + indent * (level + 1)
        else:
            element.text = newline + indent * \
                (level + 1) + element.text.strip() + \
                newline + indent * (level + 1)
            # else:  # 此处两行如果把注释去掉，Element的text也会另起一行
            # element.text = newline + indent * (level + 1) + element.text.strip() + newline + indent * level
    temp = list(element)  # 将element转成list
    for subelement in temp:
        if temp.index(subelement) < (len(temp) - 1):
            subelement.tail = newline + indent * (level + 1)
        else:
            subelement.tail = newline + indent * level
        pretty_xml(subelement, indent, newline, level=level + 1)


@click.command()
@click.option('--xml-path', '-x', default=None, type=click.STRING, help='jlink xml file path')
@click.argument('pack_path')
def main(pack_path: str, xml_path: str):
    """Import MCU Database From Cmsis Packages To JLink"""

    if pack_path == None:
        raise Exception('We need a cmsis .pack path !')

    if xml_path == None:
        p_jlink = find_exe('jlink')
        xml_path = os.path.dirname(p_jlink) + '/' + 'JLinkDevices.xml'

    if not os.path.isabs(xml_path):
        xml_path = os.path.abspath(xml_path)

    if not os.path.isabs(pack_path):
        pack_path = os.path.abspath(pack_path)

    jlink_root_dir = os.path.dirname(xml_path)

    print('-> Use cmsis package : ' + pack_path)
    print('-> Use jlink database: ' + xml_path)

    if not os.path.exists(xml_path):
        with open(to_abs_path(xml_path), 'w') as fp:
            fp.writelines(['<DataBase>', '</DataBase>'])

    cmsis_pack = CmsisPack(pack_path)

    if len(cmsis_pack.devices) == 0:
        print('Not found any device in cmsis package file !')
        exit(-1)

    print('-> Found {} devices'.format(len(cmsis_pack.devices)))

    vendor_name = cmsis_pack.devices[0].vendor
    dev_familys = cmsis_pack.devices[0].families

    xml_dom = ElementTree.parse(
        xml_path, parser=ElementTree.XMLParser(target=CommentedTreeBuilder()))
    xml_dom_db = xml_dom.getroot()

    vendor_existed_devs = []
    for node in xml_dom.iter():
        if node.tag != 'Device':
            continue
        for ele in node.iter():
            if ele.tag == 'ChipInfo' and ele.attrib.get('Vendor') == vendor_name:
                vendor_existed_devs.append(ele.attrib.get('Name'))

    print('exsited devices: ' + str(vendor_existed_devs))

    # add comment header
    if len(vendor_existed_devs) == 0:
        xml_dom_db.append(ElementTree.Comment(''))
        xml_dom_db.append(ElementTree.Comment(' {} ({}) '.format(vendor_name, dev_familys[0])))
        xml_dom_db.append(ElementTree.Comment(''))

    ign_cnt = 0

    for dev in cmsis_pack.devices:
        print('---')
        print('part: ' + dev.part_number)
        print('  vendor: ' + str(dev.vendor))
        print('  families: ' + str(dev.families))
        print('  arch: ' + dev._info.arch)
        #print('  memory_map: ' + str(dev.memory_map))

        family_name = dev.families[-1].replace(' ', '_')

        if dev.part_number in vendor_existed_devs:
            ign_cnt += 1
            print('skip duplicate device: ' + dev.part_number)
            continue

        n_ele = SubElement(xml_dom_db, 'Device')

        n_ele_cp = SubElement(n_ele, 'ChipInfo')
        ram_region = dev.memory_map.get_default_region_of_type(MemoryType.RAM)
        n_ele_cp.attrib.update({
            'Name': dev.part_number,
            'Vendor': vendor_name,
            'Core': to_jlink_core_name(dev._info.arch),
            'WorkRAMAddr': '0x{:0>8X}'.format(ram_region.start),
            'WorkRAMSize': '0x{:0>8X}'.format(ram_region.length)})

        for rom in dev.memory_map.regions:
            if not (rom.type == MemoryType.ROM or rom.type == MemoryType.FLASH):
                continue
            try:
                flm_ele = dev._find_matching_algo(rom)
                n_ele_fbi = SubElement(n_ele, 'FlashBankInfo')
                name = '{} ({})'.format(rom.name, rom.type.name)
                if rom.is_boot_memory:
                    name = '{} (Internal Flash)'.format(rom.name)
                algo_src_repath = flm_ele.attrib['name']
                algo_dst_repath = 'Devices/{}/{}/{}'.format(
                    vendor_name, family_name, os.path.basename(algo_src_repath))
                n_ele_fbi.attrib.update({
                    'Name': name,
                    'BaseAddr': '0x{:0>8X}'.format(rom.start),
                    'MaxSize': '0x{:0>8X}'.format(rom.length),
                    'Loader': algo_dst_repath,
                    'LoaderType': 'FLASH_ALGO_TYPE_OPEN'})
                bin_data = cmsis_pack.get_file(algo_src_repath)
                dst_path = jlink_root_dir + '/' + algo_dst_repath
                Path(os.path.dirname(dst_path)).mkdir(
                    parents=True, exist_ok=True)
                print('dump FLM: ' + dst_path)
                with open(dst_path, 'wb') as fp:
                    fp.write(bin_data.read())
            except KeyError:
                print('skip, not found algo for region: ' + rom.name)
                pass

    pretty_xml(xml_dom_db, '  ', '\n', 0)
    xml_dom.write(xml_path)

    print('-' * 45)
    print('All Done, added {}, ignored: {}'.format(
        len(cmsis_pack.devices) - ign_cnt, ign_cnt))
    print('-' * 45)


def to_jlink_core_name(cortex_name: str):
    # ref https://wiki.segger.com/Open_Flashloader#Extending_an_Existing_Device
    extra_map = {
        'cortex-m0+': 'JLINK_CORE_CORTEX_M0',
        'cortex-m0plus': 'JLINK_CORE_CORTEX_M0',
    }
    return extra_map.get(cortex_name,
                         'JLINK_CORE_{}'.format(cortex_name.replace('-', '_').upper()))

# ===== utility func =====


def get_script_root():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    elif __file__:
        return os.path.dirname(__file__)
    else:
        raise Exception('error !, can not get script root !')


def to_abs_path(repath: str):
    if not os.path.isabs(repath):
        return os.path.normpath(get_script_root() + os.path.sep + repath)
    else:
        return repath


def run_cmd(cmd: str, encoding='ascii'):
    proc = subprocess.Popen(args=cmd,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            shell=True, cwd=get_script_root(), encoding=encoding)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise Exception('exec "{}" failed !'.format(cmd))
    return stdout.split('\n')


def run_exe(exec_path: str, args: list, encoding='ascii'):
    return run_cmd([exec_path] + args, encoding)


def find_exe(exe_name: str):
    try:
        if sys.platform == 'win32':
            return run_cmd('where ' + exe_name)[0]
        else:
            return run_cmd('which ' + exe_name)[0]
    except Exception:
        raise Exception('cannot find file "{}" in sys path'.format(exe_name))


if __name__ == '__main__':
    main()
