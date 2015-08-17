function urlForImg(img, append) {
    var uri = img.uri;
    var ret = uri.replace(/^http:\/\/photo.bigasterisk.com/, '');
    if (append) {
        ret = ret + "/" + append;
    }
    return ret;
}




/*
Lots of code in here is to support jumping to a new image before the
last one's tags have been saved. They get queued and saved. The status
display is not careful about this, and just says saving/done when
anything is getting saved.
  */
Polymer({
    is: 'photo-tag-edit',
    properties: {
        img: {
            type: Object,
            observer: 'imgChanged'
        },
        star: {
            // should '*' be in the list we save?
            type: Boolean,
            observer: 'tagsChanged',
            value: false
        },
        tags: {
            // array without '*'
            type: Array,
            value: []
        },
        status: { type: String, value: 'startup' }
    },
    created: function () {
        this.pendingWrites = {};
        this.writeTimeout = null;
        this.saveEnabled = false;
    },
    ready: function () {
        var self = this;
        $.getJSON('/allTags', function(result) {
            $(self.$.tags).tagit({
                autocomplete: { delay: 0 },
                availableTags: result.tags,
                singleField: true,
                singleFieldDelimeter: ' ',
                afterTagAdded: function(ev, edit) {
                    self.tagsChanged();
                },
                afterTagRemoved: function(ev, edit) {
                    self.tagsChanged();
                }
            });
            self.tagitReady = true;
        });
    },
    imgChanged: function () {
        this.loadTags();
    },
    loadTags: function () {
        // (img might already have tags attr, depending on how we loaded it)
        var self = this;
        self.status = 'loading...';
        self.saveEnabled = false;
        $.getJSON(urlForImg(this.img, 'tags'), function (result) {
            var tagString = result.tagString;
            // turns '*' tag into the star icon setting
            tagString = ' ' + tagString + ' ';
            var sansStar = tagString.replace(/ \*(?= )/g, '');
            self.star = sansStar != tagString;
            sansStar = sansStar.replace(/^ +/, '').replace(/ +$/, '');
            self.tags = sansStar.split(/\s+/);
            self.status = 'ok';
            self.saveEnabled = true;

            self.setInitialTagList(self.tags);
        });
    },
    setInitialTagList: function(tags) {
        var self = this;
        
        if (self.tagitReady) {
            $(self.$.tags).tagit('removeAll');
            self.tags.forEach(function(t) {
                $(self.$.tags).tagit('createTag', t);
            });
            // tag should be readOnly until this point, but that doesn't work:
            // https://github.com/aehlke/tag-it/issues/249
            // https://github.com/aehlke/tag-it/issues/329

        } else {
            // we might finish before /allTags did, and I don't know
            // how to update the tag list on a tagit
            setTimeout(function() { self.setInitialTagList(tags); }, 200);
        }
    },
    tagsChanged: function () {
        if (!this.saveEnabled) return;
        this.tags = $(this.$.tags).tagit('assignedTags');
        this.queueWrite();
    },
    queueWrite: function () {
        var self = this;
        // note that we might be on a different img by the time the save happens
        self.pendingWrites[self.img.uri] = {
            tags: self.tags,
            star: self.star
        };
        self.status = 'edited';
        if (self.writeTimeout) {
            clearTimeout(self.writeTimeout);
            self.writeTimeout = null;
        }
        self.writeTimeout = setTimeout(self.flushWrites.bind(self), 500);
    },
    flushWrites: function () {
        var self = this;
        $.each(self.pendingWrites, function eachWrite(uri, data) {
            self.saveTags(uri, data);
        });
        self.pendingWrites = {};
    },
    saveTags: function (uri, data) {
        var self = this;
        self.status = 'saving...';
        var fullTagString = data.tags.join(' ') + (data.star ? ' *' : '');
        $.ajax({
            type: 'PUT',
            url: urlForImg({ uri: uri }, 'tags'),
            data: { tags: fullTagString },
            success: function (data) {
                self.status = 'ok';
            },
            dataType: 'json'
        });
    }
});
