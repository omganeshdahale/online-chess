$(document).ready(function () {
  board = Chessboard("myBoard", "start");
  $(window).resize(board.resize);
});
