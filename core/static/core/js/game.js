$(document).ready(function () {
  let colour = null;

  $("#play-btn").click(function () {
    $(this).prop("disabled", true);
    $(this).html(
      `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Finding opponent...`
    );

    const chatSocket = new WebSocket(
      "ws://" + window.location.host + "/ws/game/"
    );

    chatSocket.onmessage = function (e) {
      const data = JSON.parse(e.data);

      if (data["command"] === "start") {
        $("#play-btn").hide();
        colour = data["colour"];
        const config = {
          orientation: colour,
          position: "start",
        };
        const board = Chessboard("myBoard", config);
        $(window).resize(board.resize);
      } else if (data["command"] === "abandoned") {
        alert(colour + " win by abandonment");
      }
    };

    chatSocket.onclose = function (e) {
      console.error("Chat socket closed unexpectedly");
    };
  });
});
