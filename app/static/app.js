// Lightweight YouTube embed: show a thumbnail, only load the player on click.
document.querySelectorAll(".yt-facade").forEach((el) => {
  const play = () => {
    if (el.classList.contains("is-playing")) return;
    const iframe = document.createElement("iframe");
    iframe.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(el.dataset.id)}?autoplay=1&rel=0`;
    iframe.title = el.dataset.title || "Video";
    iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
    iframe.allowFullscreen = true;
    el.replaceChildren(iframe);
    el.classList.add("is-playing");
  };
  el.addEventListener("click", play);
  el.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      play();
    }
  });
});
