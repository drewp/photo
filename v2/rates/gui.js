angular
    .module('app', [])
    .controller(
        'ctrl',
        function ($scope, $http) {
            $scope.data = {};
            $http.get('rates').then(function (result) {
                $scope.data = result.data;
            });
        }
    );
