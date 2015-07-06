import re

def lazy_xml_chunks(f, tag, chunksize=1024):
    """
    Given a file containing chunks delimited by <tagname>..</tagname>, yield
    these chunks, as strings, including the start and end tags.
    Assumes that the instances of the tags do not overlap, and that <tagname>
    will be encountered before </tagname>.
    """
    # Match either '<tag stuff> junk </tag>' or '<tag> junk </tag>'.
    startpageprog = re.compile(r'<%s [\s\S]*?>|<%s>' % (tag,tag))
    closepageprog = re.compile(r'</%s>' % tag)
    
    buffer = ''

    while True:
        starts = [m.start() for m in startpageprog.finditer(buffer) if m]
        ends = [m.end() for m in closepageprog.finditer(buffer) if m]
        chunks = zip(starts[:len(ends)], ends)
        if len(chunks):
            for start, end in chunks:
                yield buffer[start:end]
            last_end = chunks[-1][1]
            buffer = buffer[last_end:]
        # need to read more data
        data = f.read(chunksize)
        if data == '':
            break
        buffer += data
