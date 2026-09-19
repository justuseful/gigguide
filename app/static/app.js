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

// Typeahead combobox for picking a venue (single) or performers (multiple) by
// name instead of scrolling a long <select>/checkbox list. Each instance reads
// its option list and initial selection from adjacent JSON <script> tags, and
// writes plain hidden inputs so the surrounding <form> submits exactly as it
// did before (venue_id=<id>, performer_ids=<id> repeated).
document.querySelectorAll("[data-combobox]").forEach((root) => {
  const mode = root.dataset.combobox;
  const fieldName = root.dataset.name;
  const options = JSON.parse(root.querySelector(".combobox__options").textContent);
  const initial = JSON.parse(root.querySelector(".combobox__selected").textContent);
  const input = root.querySelector(".combobox__input");
  const list = root.querySelector(".combobox__list");
  const hidden = root.querySelector(".combobox__hidden");
  const chips = root.querySelector(".combobox__chips");

  const selected = new Map(); // id -> label
  let selectedLabel = "";

  function addHiddenInput(id) {
    const inp = document.createElement("input");
    inp.type = "hidden";
    inp.name = fieldName;
    inp.value = id;
    inp.dataset.optionId = id;
    hidden.appendChild(inp);
  }

  function clearHiddenInputs() {
    hidden.querySelectorAll("input").forEach((inp) => inp.remove());
  }

  function renderChips() {
    chips.innerHTML = "";
    selected.forEach((label, id) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.append(label);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "chip__remove";
      remove.setAttribute("aria-label", `Remove ${label}`);
      remove.textContent = "×";
      remove.addEventListener("click", () => {
        selected.delete(id);
        hidden.querySelector(`input[data-option-id="${id}"]`)?.remove();
        renderChips();
      });
      chip.appendChild(remove);
      chips.appendChild(chip);
    });
  }

  function closeList() {
    list.hidden = true;
    list.innerHTML = "";
  }

  function choose(opt) {
    if (mode === "multi") {
      if (!selected.has(opt.id)) {
        selected.set(opt.id, opt.label);
        addHiddenInput(opt.id);
        renderChips();
      }
      input.value = "";
    } else {
      selectedLabel = opt.label;
      input.value = opt.label;
      clearHiddenInputs();
      addHiddenInput(opt.id);
    }
    closeList();
  }

  function openList(matches) {
    list.innerHTML = "";
    if (matches.length === 0) {
      const li = document.createElement("li");
      li.className = "combobox__empty";
      li.textContent = "No matches";
      list.appendChild(li);
    } else {
      matches.slice(0, 50).forEach((opt) => {
        const li = document.createElement("li");
        li.className = "combobox__option";
        li.setAttribute("role", "option");
        li.textContent = opt.label;
        li.addEventListener("mousedown", (e) => {
          e.preventDefault(); // fires before blur, so the list is still open
          choose(opt);
        });
        list.appendChild(li);
      });
    }
    list.hidden = false;
  }

  function search() {
    const term = input.value.trim().toLowerCase();
    if (!term) {
      closeList();
      return;
    }
    const available = mode === "multi" ? options.filter((o) => !selected.has(o.id)) : options;
    openList(available.filter((o) => o.label.toLowerCase().includes(term)));
  }

  initial.forEach((opt) => {
    if (mode === "multi") {
      selected.set(opt.id, opt.label);
      addHiddenInput(opt.id);
    } else {
      selectedLabel = opt.label;
      addHiddenInput(opt.id);
    }
  });
  if (mode === "multi") renderChips();

  input.addEventListener("input", search);
  input.addEventListener("focus", () => {
    if (input.value.trim()) search();
  });
  input.addEventListener("blur", () => {
    // Delay so a mousedown on an option (which preventDefault()s blur's
    // default action but not blur itself) can run its handler first.
    setTimeout(() => {
      closeList();
      if (mode === "single") input.value = selectedLabel;
    }, 150);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeList();
    if (e.key === "Enter" && !list.hidden) {
      e.preventDefault();
      list.querySelector(".combobox__option")?.dispatchEvent(new MouseEvent("mousedown"));
    }
  });
});
