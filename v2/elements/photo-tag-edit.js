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
Polymer("photo-tag-edit", {
    created: function() {
        this.status = 'startup';
        this.tags = '';
        this.star = false;

        this.pendingWrites = {};
        this.writeTimeout = null;
        this.saveEnabled = false;
    },
    domReady: function() {
        var self = this;
      
        // tag.js does a re-focus() after it edits the contents, and
        // we were missing those edits before.
        self.$.tags.addEventListener('focus', function () {
            self.tags = self.$.tags.value;
        });
        
        //allTags = JSON.parse(d.allTags);
        var allTags = ['one', 'two', 'three', 'four', 'five'];
        setGlobalTags(allTags);
        $(self.$.tags).tagSuggest({});
    },
    imgChanged: function() {
        if (typeof this.img == 'string') {
            this.img = {uri: this.img};
        }
        this.loadTags();
    },
    loadTags: function() {
        // (img might already have tags attr, depending on how we loaded it)
        var self = this;
        
        self.status = 'loading...';
        self.saveEnabled = false;
        $.getJSON(urlForImg(this.img, 'tags'), function (result) {
            var tagString = result.tagString;

            // turns '*' tag into the star icon setting
            tagString = " " + tagString + " ";
            var sansStar = tagString.replace(/ \*(?= )/g, "");

            self.star = sansStar != tagString;

            sansStar = sansStar.replace(/^ +/, "").replace(/ +$/, "");
            self.tags = sansStar;
            self.loadTags = self.tags;
            self.status = 'ok';
            self.saveEnabled = true;
        });
    },
    tagsChanged: function() {
        if (this.loadTags === this.tags) {
            return;
        }
        if (this.saveEnabled) {
            this.queueWrite();
        }
    },
    starChanged: function() {
        if (this.saveEnabled) {
            this.queueWrite();
        }
    },
    queueWrite: function() {
        var self = this;
        // note that we might be on a different img by the time the save happens
        self.pendingWrites[self.img.uri] = {tags: self.tags, star: self.star};
        self.status = 'edited';
        if (self.writeTimeout) {
            clearTimeout(self.writeTimeout);
            self.writeTimeout = null;
        }
        self.writeTimeout = setTimeout(self.flushWrites.bind(self), 500);
    },
    flushWrites: function() {
        var self = this;
        $.each(self.pendingWrites, function eachWrite(uri, data) {
            self.saveTags(uri, data);
        });
        self.pendingWrites = {};
    },
    saveTags: function(uri, data) {
        var self = this;
        self.status = 'saving...';

        var fullTagString = data.tags + (data.star ? " *" : "");
        $.ajax({
            type: 'PUT',
            url: urlForImg({uri: uri}, "tags"),
            data : {
                tags: fullTagString
            },
            success: function(data) {
                self.status = 'ok';
            },
            dataType: "json",
        });
    }
});
