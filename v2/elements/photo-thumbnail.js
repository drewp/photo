Polymer("photo-thumbnail", {
    ready: function() {
        var self = this;
        self.imgSrc = self.img.uri.replace('http://', 'https://') + '?size=small';
        // video marker, uri link, click action
        // preload control, etc
    }
});
