Polymer("photo-thumbnail", {
    ready: function() {
        var self = this;
        if (typeof self.img == 'string') {
            self.img = {uri: self.img};
        }
        self.imgSrc = self.img.uri.replace('http://', 'https://') + '?size=small';
        // video marker, uri link, click action
        // preload control, etc
    }
});
