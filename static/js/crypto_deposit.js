document.addEventListener("DOMContentLoaded", function () {
  var qrContainer = document.getElementById("crypto-qr");
  if (!qrContainer) {
    return;
  }

  var address = qrContainer.getAttribute("data-address");
  if (!address) {
    return;
  }

  if (window.QRCode) {
    qrContainer.innerHTML = "";
    new QRCode(qrContainer, {
      text: address,
      width: 200,
      height: 200,
    });
  } else {
    qrContainer.textContent = address;
  }
});
