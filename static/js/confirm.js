// O'chirish va rad etish kabi qaytarib bo'lmaydigan amallar uchun tasdiqlash so'raydi.
// Forma ustiga data-confirm="..." atributi qo'yilsa yetarli.

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.dataset.confirm)) {
        event.preventDefault();
      }
    });
  });
});
