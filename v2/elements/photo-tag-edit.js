function urlForImg(img, append) {
    var uri = img.uri;
    var ret = uri.replace(/^http:\/\/photo.bigasterisk.com/, '');
    if (append) {
        ret = ret + "/" + append;
    }
    return ret;
}


/*
Wrapper on tagit that can be used before setAvailableTags is called,
even though the real widget is only created at setAvailableTags time
(since I don't know how to update its available-tag list)
*/
function TagitWidget(elem, onTagsChanged) {
    this.t = null;
    this.elem = elem;
    this.onTagsChanged = onTagsChanged;
    this.initialTags = [];
    this.initialOnDone = null;
}
TagitWidget.prototype.setAvailableTags = function(availableTags) {
    if (this.t !== null) throw new Error("already setAvailableTags");
    this.t = $(this.elem).tagit({
        autocomplete: { delay: 0 },
        availableTags: availableTags,
        singleField: true,
        singleFieldDelimeter: ' ',
        afterTagAdded: function(ev, edit) {
            this.onTagsChanged();
        }.bind(this),
        afterTagRemoved: function(ev, edit) {
            this.onTagsChanged();
        }.bind(this)
    });

    // this may not have any effect
    var i = this.elem.parentElement.querySelector("input.ui-autocomplete-input");
    i.setAttribute('autocapitalize', 'none');
    
    this.setTags(this.initialTags, this.initialOnDone);
};
TagitWidget.prototype.setTags = function(tags, onDone) {
    if (this.t == null) {
        this.initialTags = tags;
        this.initialOnDone = onDone;
        return;
    }
    
    this.t.tagit('removeAll');
    tags.forEach(function(tag) {
        this.t.tagit('createTag', tag);
    }.bind(this));
    if (onDone) {
        onDone();
    }
};
TagitWidget.prototype.getTags = function() {
    if (this.t == null) {
        return this.initialTags;
    }
    return this.t.tagit('assignedTags')
};


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
        self.widget = new TagitWidget(self.$.tags, self.tagsChanged.bind(self));

        // todo: these may be available in a page global already
        $.getJSON('/allTags', function(result) {
            self.widget.setAvailableTags(result.tags);
        });
        self.$.desc.addEventListener('value-changed', self.tagsChanged.bind(self))
    },
    imgChanged: function () {
        this.loadTags();
    },

    loadTags: function () {
        // (img might already have tags attr, depending on how we loaded it)
        var self = this;
        self.status = 'loading...';
        self.saveEnabled = false;
        $.getJSON(urlForImg(self.img, 'tags'), function (result) {
            var tagString = result.tagString;
            // turns '*' tag into the star icon setting
            tagString = ' ' + tagString + ' ';
            var sansStar = tagString.replace(/ \*(?= )/g, '');
            self.star = sansStar != tagString;
            sansStar = sansStar.replace(/^ +/, '').replace(/ +$/, '');
            self.tags = sansStar.split(/\s+/);
            self.widget.setTags(self.tags, function() {
                self.saveEnabled = true;
            });
            self.$.desc.value = result.desc;
            self.status = 'ok';
            // tag should be readOnly until this point, but that doesn't work:
            // https://github.com/aehlke/tag-it/issues/249
            // https://github.com/aehlke/tag-it/issues/329
        });
    },
    tagsChanged: function () {
        if (!this.saveEnabled) return;
        this.tags = this.widget.getTags();
        this.queueWrite();
    },
    queueWrite: function () {
        var self = this;
        // note that we might be on a different img by the time the save happens
        self.pendingWrites[self.img.uri] = {
            tags: self.tags,
            star: self.star,
            desc: self.$.desc.value
        };
        self.status = 'edited';
        if (self.writeTimeout) {
            clearTimeout(self.writeTimeout);
            self.writeTimeout = null;
        }
        self.writeTimeout = setTimeout(self.flushWrites.bind(self), 500);
    },
    flushWrites: function () {
        $.each(this.pendingWrites, function eachWrite(uri, data) {
            this.saveTags(uri, data);
        }.bind(this));
        this.pendingWrites = {};
    },
    fullTagString: function(tags, star) {
        return tags.join(' ') + (star ? ' *' : '');
    },
    saveTags: function (uri, data) {
        this.status = 'saving...';
        var fullTagString = this.fullTagString(data.tags, data.star);
        $.ajax({
            type: 'PUT',
            url: urlForImg({ uri: uri }, 'tags'),
            data: { tags: fullTagString,
                    desc: data.desc },
            success: function (data) {
                this.status = 'ok';
                this.fire("tags-saved");
            }.bind(this),
            dataType: 'json'
        });
    }
});
