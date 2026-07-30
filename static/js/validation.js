// Forma tekshiruvi — faqat tezkor UX uchun.
// Yakuniy tekshiruv baribir serverda (Pydantic schema va service qatlami) bajariladi.

const MIN_LESSON_DURATION = 300;
const MAX_LESSON_DURATION = 600;
const KINESCOPE_DOMAIN = "kinescope.io";

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-validate-lesson]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      const problem = findLessonFormProblem(form);
      if (problem) {
        event.preventDefault();
        alert(problem);
      }
    });
  });
});

function findLessonFormProblem(form) {
  const duration = Number(form.querySelector("[name='duration_seconds']").value);
  if (duration < MIN_LESSON_DURATION || duration > MAX_LESSON_DURATION) {
    return "Dars davomiyligi 300–600 soniya (5–10 daqiqa) oralig'ida bo'lishi kerak.";
  }

  const videoUrl = form.querySelector("[name='kinescope_url']").value;
  if (videoUrl.indexOf(KINESCOPE_DOMAIN) === -1) {
    return "Video havolasi kinescope.io domenida bo'lishi kerak.";
  }

  return null;
}
