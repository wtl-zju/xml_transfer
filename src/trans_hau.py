#-*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf8')
import sys
import os
import StringIO

from lxml import etree


class Tree(object):
    """
    Abstract base class for classes representing annotation documents.
    Supports both reading from and writing to XML.
    Inputs
    ------
    tree : lxml.etree.ElementTree
        ElementTree representing the XML document.
    Attributes
    ----------
    xml_version : str
        XML version of document.
    doc_type : str
        XML document type declaration.
    doc_id : str
        Document id.
    lang : lang
        Document language.
    """
    def __init__(self, tree):
        self.tree = tree
        self.xml_version = self.tree.docinfo.xml_version
        self.doc_type = self.tree.docinfo.doctype
        doc_elem = self.tree.find('//DOC')
        self.doc_id = doc_elem.get('id')
        self.lang = doc_elem.get('lang')
        if self.lang is None:
            self.lang = ''  # some version can have no lang attribute

    def write_to_file(self, xmlf):
        """
        write document to file as XML in the correct format
        :param xmlf: output file for XML
        :return:
        """
        self.tree.write(xmlf, encoding='utf-8', pretty_print=True, xml_declaration=True)


class LTFDocument(Tree):
    """
    supports reading/writing of LCTL text format (LTF) files.
     Inputs
    ------
    xmlf : str
        LTF XML file to read.
    Attributes
    ----------
    tree : lxml.etree.ElementTree
        ElementTree representing the XML document.
    xml_version : str
        XML version of document.
    doc_type : str
        XML document type declaration.
    doc_id : str
        Document id.
    lang : lang
        Document language.
    """
    def __init__(self, xmlf, segment=None, doc_id=None):
        def xor(a, b):
            return a + b == 1
        assert(xor(xmlf is not None, segment is not None))
        if not xmlf is None:
            tree = etree.parse(xmlf)
        else:
            base_xml = """<?xml version='1.0' encoding='UTF-8'?>
                          <!DOCTYPE LCTL_TEXT SYSTEM "ltf.v1.5.dtd">
                          <LCTL_TEXT/>
                       """
            tree = etree.parse(StringIO.StringIO(base_xml))
            root = tree.getroot()

            # Create and set attributes on doc node.
            doc = etree.SubElement(root, 'DOC')
            doc.set('id', doc_id)

            text = etree.SubElement(doc, 'TEXT')
            seg = etree.SubElement(text, 'SEG')
            text.replace(seg, segment)


        super(LTFDocument, self).__init__(tree)

    def segments(self):
        """Lazily generate segments present in LTF document.
        Outputs
        -------
        segments : lxml.etree.ElementTree generator
            Generator for segments, each represented by an ElementTree.
        """
        for segment in self.tree.xpath('//SEG'):
            yield segment

    def tokenized(self):
        """Extract tokens.
        All returned indices assume 0-indexing.
        Outputs
        -------
        tokens : list of str
            Tokens.
        token_ids : list of str
            Token ids.
        token_onsets : list of int
            Character onsets of tokens.
        token_offsets : list of int
            Character offsets of tokens.
        """
        tokens = []
        token_ids = []
        token_onsets = []
        token_offsets = []
        for seg_ in self.segments():
            for token_ in seg_.xpath('.//TOKEN'):
                tokens.append(token_.text)
                token_ids.append(token_.get('id'))
                token_onsets.append(token_.get('start_char'))
                token_offsets.append(token_.get('end_char'))
        tokens = [' ' if token is None else token for token in tokens]
        token_onsets = [token_onset if token_onset is None else int(token_onset) for token_onset in token_onsets]
        token_offsets = [token_offset if token_offset is None else int(token_offset) for token_offset in token_offsets]
        return tokens, token_ids, token_onsets, token_offsets

    def text(self):
        """Return original text of document.
        """
        text = [elem.text for elem in self.tree.xpath('//ORIGINAL_TEXT')]
        text = u' '.join(text)
        return text


class LAFDocument(Tree):
    """Supports reading/writing of LCTL annotation format (LAF) files.
    Inputs
    ------
    xmlf : str, optional
        LAF XML file to read. If not provided, the document will be initialized
        from supplied mentions.
    mentions : list of tuples, optional
        List of mention tuples. For format, see mentions method docstring.
    lang : str, optional
        Document language.
    doc_id : str, optional
        Document id.
    Attributes
    ----------
    tree : lxml.etree.ElementTree
        ElementTree representing the XML document.
    xml_version : str
        XML version of document.
    doc_type : str
        XML document type declaration.
    doc_id : str
        Document id.
    lang : str
        Document language.
    """
    def __init__(self, xmlf=None, mentions=None, lang=None, doc_id=None):
        def xor(a, b):
            return a + b == 1
        assert(xor(xmlf is not None, mentions is not None))
        if not xmlf is None:
            tree = etree.parse(xmlf)
        else:
            base_xml = """<?xml version='1.0' encoding='UTF-8'?>
                          <!DOCTYPE LCTL_ANNOTATIONS SYSTEM "laf.v1.2.dtd">
                          <LCTL_ANNOTATIONS/>
                       """

            # Create and set attributes on root node.
            tree = etree.parse(StringIO.StringIO(base_xml))
            root = tree.getroot()
            root.set('lang', lang)

            # Create and set attributes on doc node.
            doc = etree.SubElement(root, 'DOC')
            doc.set('id', doc_id)
            doc.set('lang', lang)

            # And for all the mentions.
            for entity_id, type, extent, start_char, end_char in mentions:
                # <ANNOTATION>...</ANNOTATION>
                annotation = etree.SubElement(doc, 'ANNOTATION')
                annotation.set('id', entity_id)
                annotation.set('task', 'NE')  # move to constant or arg?
                annotation.set('type', type)
                # <EXTENT>...</EXTENT>
                extent_elem = etree.SubElement(annotation, 'EXTENT')
                extent_elem.text = extent
                extent_elem.set('start_char', str(start_char))
                extent_elem.set('end_char', str(end_char))

        super(LAFDocument, self).__init__(tree)

    def annotations(self):
        """Lazily generate annotations present in LAF document.
        Outputs
        -------
        annotations : lxml.etree.ElementTree generator
            Generator for annotations, each represented by an ElementTree.
        """
        for annotation in self.tree.xpath('//ANNOTATION'):
            yield annotation
    def mentions(self):
        """Extract mentions.
        Returns a list of mention tuples, each of the form:
        (entity_id, tag, extent, start_char, end_char)
        where entity_id is the entity id, tag the annotation tag,
        extent the text extent (a string) of the mention in the underlying
        RSD file, start_char the character onset (0-indexed) of the mention,
        and end_char the character offset (0-indexed) of the mention.
        """
        mentions = []
        for mention_ in self.tree.xpath('//ANNOTATION'):
            entity_id = mention_.get('id')
            type = mention_.get('type')
            extent = mention_.xpath('EXTENT')[0]
            start_char = int(extent.get('start_char'))
            end_char = int(extent.get('end_char'))

            mention = [entity_id,
                       type,
                       extent,
                       start_char,
                       end_char]
            mentions.append(mention)

        return mentions


def load_doc(xmlf, cls):
    """Parse xml file and return document.
    This is a helper function intended to help debugging.
    Inputs
    ------
    xmlf : str
        XML file to open.
    cls : Tree class
        Subclass of Tree.
    logger : logging.Logger
        Logger instance.
    """
    try:
        assert(os.path.exists(xmlf))
        doc = cls(xmlf)
    except KeyError:
        doc = None
    return doc

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print 'USAGE: python trans_hau.py <ltf dir> <laf dir><ltf_split file> <laf_split file>'
        print 'this script will split LDC ltf and laf document file to sentences, it is suitable for yoruba and tamil'
    else:
        ltf_dir = sys.argv[1]
        laf_dir = sys.argv[2]
        ltf_split_result_path = sys.argv[3]
        laf_split_result_path = sys.argv[4]
    # ltf_split_result_path = './data/Yoruba_data/annotation/entity_annotation/simple/with_tone/ltf_split'
    # laf_split_result_path = './data/Yoruba_data/annotation/entity_annotation/simple/with_tone/laf_split'


        ltf_files = []
        laf_files = []
        for root, dirs, files in os.walk(ltf_dir):
            for f in files:
                print f
                if f.find('ltf') > 0:
                    temp = ltf_dir+'/'+f
                    ltf_files.append(temp)
                    laf_files.append(temp.replace('ltf', 'laf'))  # search every file in ltf and laf
        print ltf_files
        for k in range(len(ltf_files)):
        # for k in range(1):
            print 'k: ' + str(k)
            ltf_path = ltf_files[k]
            laf_path = laf_files[k]
            ltf_doc = load_doc(ltf_path, LTFDocument)
            laf_doc = load_doc(laf_path, LAFDocument)
            segments = ltf_doc.segments()   # load the ltf and laf files and the segments in ltf file
            j = 0
            doc_id = ltf_doc.doc_id
            for segment in segments:
                print 'j: ' + str(j)
                ltff = ltf_split_result_path+'/'+doc_id +'_'+segment.get('id')+'.'+'ltf.xml'
                laff = laf_split_result_path+'/'+doc_id +'_'+segment.get('id')+'.'+'laf.xml'
                ltf_temp = LTFDocument(xmlf=None, segment=segment, doc_id=doc_id +'_'+segment.get('id'))
                ltf_temp.write_to_file(ltff)  # finish ltf file

                mentions = []
                i = 0
                ltf_start_char = segment.get('start_char')
                ltf_end_char = segment.get('end_char')
                annotations = laf_doc.annotations()
                for annotation in annotations:
                    laf_start_char = annotation.xpath('EXTENT')[0].get('start_char')
                    laf_end_char = annotation.xpath('EXTENT')[0].get('end_char')
                    ########
                    # if start_char > -1 and end_char == -1:
                    #     print 'find wrong start char'
                    # if end_char > -1 and start_char == -1:
                    #     print 'find wrong end char'
                    ############
                    if int(ltf_end_char)>=int(laf_end_char) and int(ltf_start_char) <= int(laf_start_char):
                        print 'this is ltf_start_char'+ltf_start_char
                        print 'this is ltf_end_char'+ltf_end_char
                        print 'this is laf_start_char'+ laf_start_char
                        print 'this is laf_end_char'+ laf_end_char
                        #print 'start char' + str(start_char) + 'end char' + str(end_char)
                        entity_id = annotation.get('id')
                        type = annotation.get('type')
                        extent = annotation.xpath('EXTENT')[0]
                        extent_text = extent.text

                        mention = [entity_id,
                                   type,
                                   extent_text,
                                   laf_start_char,
                                   laf_end_char]
                        mentions.append(mention)
                    else:
                        pass
                    i += 1
                laf_temp = LAFDocument(xmlf=None, mentions=mentions, lang=laf_doc.lang, doc_id=doc_id +'_'+segment.get('id'))
                laf_temp.write_to_file(laff)
                j += 1



                





