#!/usr/bin/python
"""
read an email message on stdin; write any image attachments to the
photo library.

usage:
for x (/my/mail/drewp/.newphoto/cur/*) { cat $x | ./ingestmail }

associate metadata about the email with the images
"""

import boot
import maillib

import datetime, os, logging, sys, urllib, restkit
from dateutil.tz import tzlocal
from remotesparql import RemoteSparql
import networking
from rdflib import URIRef, Literal
from scanFs import uriOfFilename
from ns import PHO, SITE, FOAF, DCTERMS, RDFS, RDF

log = boot.log
log.setLevel(logging.INFO)

def writeExcl(path, content):
    log.info("writing %r", path)
    fd = os.open(path, os.O_WRONLY | os.O_EXCL | os.O_CREAT, 0644)
    os.write(fd, content)
    os.close(fd)

def filenameAttempts(filename, outDir):
    for suffix in [''] + ['.%d' % i for i in range(1000)]:
        root, ext = os.path.splitext(filename.replace(" ","_"))
        outFilename = root + suffix + ext
        outPath = os.path.join(outDir, outFilename)
        yield outPath

def getGraph():
    return RemoteSparql(networking.graphRepoRoot(),
                        "photo",
                        initNs=dict(foaf=FOAF,
                                    rdfs=RDFS.RDFSNS,
                                    pho=PHO))

def emailStatements(uri, msg):
    sender = URIRef("mailto:" + msg.sender[1]) # quote?

    # i think this is doing double-timezone offsets
    created = msg.date.replace(tzinfo=tzlocal())

# Date: Sat, 06 Aug 2011 20:57:57 -0700
# became 2011-08-07T03:57:57-07:00
    
    return [
        (uri, RDF.type, PHO['Email']),
        (uri, DCTERMS.creator, sender),
        (sender, RDFS.label, Literal(msg.sender[1])),
        (sender, FOAF.name, Literal(msg.sender[0])),
        (uri, DCTERMS.created, Literal(created)),
        (uri, DCTERMS.date, Literal(created.date())),
    ]

def findAttachments(msg):
    return [(f, c) for f, c in msg.attachments()
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]

def ingest(fileObj, mock=False, newImageCb=lambda uri: None):
    #f = open("/my/mail/drewp/cur/1283804816.32729_0.bang:2,S")
    msg = maillib.Message.from_file(fileObj)

    attachments = findAttachments(msg)
    if not attachments:
        log.info("no attachments with image extensions")
        return

    uri = URIRef("mid:" + urllib.quote(msg.headers['Message-ID'].strip('<>')))

    msgDate = msg.date.date().isoformat()
    now = Literal(datetime.datetime.now(tzlocal()))

    sesameImport = restkit.Resource("http://bang:9042/", timeout=5)
    stmts = emailStatements(uri, msg)
    errs = []
    for filename, content in attachments:
        outDir = "/my/pic/email/%s" % msgDate
        if not os.path.isdir(outDir):
            os.mkdir(outDir)

        for outPath in filenameAttempts(filename, outDir):
            img = uriOfFilename(rootUri=URIRef(SITE.rstrip('/')),
                                root='/my/pic',
                                filename=outPath)
            if os.path.exists(outPath) and open(outPath).read() == content:
                log.info("already wrote this to %s" % outPath)
            else:
                try:
                    if not mock:
                        writeExcl(outPath, content)
                        # jhead -autorot might be good to run on the result
                except OSError, e:
                    log.error(e)
                    continue # next suffix attempt

            stmts.extend([
                (uri, DCTERMS['hasPart'], img),
                (img, PHO['filenameInEmail'], Literal(filename)),
                (img, PHO['emailReadTime'], now),
                ])

            log.info("  described new image: %s", img)
            try:
                newImageCb(img)
            except Exception, e:
                log.error("newImageCb failed on %r: %s" % (img, e))
            if not mock:
                log.debug("  post to sesameImport")
                sesameImport.post(file=outPath)
            break
        else:
            errs.append(e)
            

    ctx = SITE['fromEmail/%s' % uri[4:]] # (already quoted above)
    graph = getGraph()
    if not mock:
        graph.add(*stmts, **{'context' : ctx})
    log.info("added %s statements about %s to context %s", len(stmts), uri, ctx)

    if errs:
        log.error("Some files could not be written: %s" % errs)
        raise errs[0]

def main():
    ingest(sys.stdin)

if __name__ == '__main__':
    main()
