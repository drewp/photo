angular.module("photo", ["photo.random"]).directive("thumb", ->
  restrict: "E"
  scope: {
    uri: '@'
  }
  controller: ($scope, $element, $attrs) ->
    console.log("see", $attrs.uri)

  template: """
  <div class="thumb">
    <a href="{{uri}}"><img ng-src="{{uri}}?size=thumb"></a>
  </div>
    """
  replace: true
)

angular.module("photo.random", ['ngResource']).factory('Randoms', ($resource) ->
  $resource('random', {}, {
    query: {method: 'GET', params: {}}
  })
)