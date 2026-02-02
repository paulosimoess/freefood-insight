<script>
  let file = null;
  let loading = false;
  let error = "";
  let data = null;

  let showImages = false;
  let showTech = false;

  let modalOpen = false;
  let modalSrc = "";
  let modalTitle = "";

  const API_BASE = import.meta.env.VITE_API_BASE ?? "";

  function onFileChange(e) {
    error = "";
    data = null;
    file = e.target.files?.[0] ?? null;
  }

  function friendlyError(msg) {
    const m = (msg || "").toLowerCase();

    if (m.includes("no plate detected")) {
      return "Não foi possível detetar o prato. Tenta uma imagem com o prato mais visível.";
    }
    if (m.includes("error in object detection")) {
      return "Ocorreu um erro na deteção. Tenta novamente (ou usa outra imagem).";
    }
    if (m.includes("http 413")) {
      return "A imagem é demasiado grande. Tenta uma versão mais pequena.";
    }
    return msg || "Erro ao calcular.";
  }

  async function calculate() {
    if (!file) {
      error = "Seleciona uma imagem primeiro.";
      return;
    }

    loading = true;
    error = "";
    data = null;

    try {
      const fd = new FormData();
      fd.append("file", file);

      const res = await fetch(`${API_BASE}/api/calories`, {
        method: "POST",
        body: fd
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `Erro HTTP ${res.status}`);
      }

      data = await res.json();
      showImages = false;
      modalOpen = false;
    } catch (e) {
      error = friendlyError(e?.message);
    } finally {
      loading = false;
    }
  }

  function goBack() {
    try {
      history.back();
    } catch {
      window.location.href = "/";
    }
  }

  const CAL_FORMULA = "kcal = (kcal/100g ÷ 100) × gramas_estimadas";
  const WASTE_FORMULA = "W = FoodArea / (PlateArea − GarbageArea) × 100";

  function openModal(title, base64) {
    modalTitle = title;
    modalSrc = `data:image/jpeg;base64,${base64}`;
    modalOpen = true;
  }

  function closeModal() {
    modalOpen = false;
    modalSrc = "";
    modalTitle = "";
  }

  function onKeydown(e) {
    if (e.key === "Escape" && modalOpen) closeModal();
  }
</script>

<svelte:window on:keydown={onKeydown} />

<main class="w-screen min-h-screen bg-zinc-900 text-zinc-200 px-6 py-10">
  <div class="w-full max-w-[1950px] mx-auto space-y-6">
    <div class="flex items-start justify-between gap-4">
      <button
        class="px-4 py-2 rounded-xl font-semibold border border-zinc-700 hover:border-zinc-500 hover:opacity-90"
        on:click={goBack}
        type="button"
      >
        ← Voltar
      </button>

      <div class="text-right">
        <h1 class="text-2xl sm:text-3xl font-bold">Contador de Calorias</h1>
        <p class="text-sm text-zinc-400">
          Upload → deteção → estimativa por porção (área relativa no prato)
        </p>
        <p class="text-xs text-zinc-500 mt-1">
          Nota: estes valores são estimativas aproximadas e dependem da deteção automática.
        </p>
      </div>
    </div>

    <!-- BODY GRID -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
      <!-- LEFT CARD: fórmulas + explicação -->
      <aside class="lg:col-span-4 rounded-2xl border border-zinc-800 bg-zinc-950/30 p-5 space-y-4">
        <div>
          <h2 class="font-semibold text-lg">
            <span class="text-red-700">Como</span> calculamos
          </h2>
          <p class="text-sm text-zinc-400 mt-1">
            Resumo simples das regras usadas para estimar calorias e desperdício.
          </p>
        </div>

        <div class="space-y-2">
          <p class="text-sm">
            <span class="text-red-700 font-semibold">Calorias</span>
          </p>
          <div class="font-mono text-sm rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
            {CAL_FORMULA}
          </div>
          <ul class="text-sm text-zinc-400 list-disc pl-5 space-y-1">
            <li><b>kcal/100g</b> vem do mapa de alimentos.</li>
            <li><b>gramas_estimadas</b> é a porção estimada pela área relativa no prato.</li>
            <li>Usamos limites de sanidade para evitar valores absurdos.</li>
          </ul>
        </div>

        <div class="space-y-2 pt-2 border-t border-zinc-800">
          <p class="text-sm">
            <span class="text-red-700 font-semibold">Desperdício</span>
          </p>
          <div class="font-mono text-sm rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
            {WASTE_FORMULA}
          </div>
          <ul class="text-sm text-zinc-400 list-disc pl-5 space-y-1">
            <li>Calculado em <b>pixéis</b> a partir das deteções.</li>
            <li>Utensílios e “garbage” são ignorados.</li>
            <li>O prato é a referência para normalizar a área.</li>
          </ul>
        </div>

        {#if data}
          <div class="pt-2 border-t border-zinc-800 space-y-2">
            <p class="text-sm">
              <span class="text-red-700 font-semibold">Valores atuais</span>
            </p>
            <div class="text-sm text-zinc-400 space-y-1">
              <div>FoodArea: <b class="text-zinc-200">{(data.food_area ?? 0).toFixed(2)}</b></div>
              <div>PlateArea: <b class="text-zinc-200">{(data.plate_area ?? 0).toFixed(2)}</b></div>
              <div>GarbageArea: <b class="text-zinc-200">{(data.garbage_area ?? 0).toFixed(2)}</b></div>
            </div>
          </div>
        {/if}
      </aside>

      <!-- CENTER: upload + resultados -->
      <section class="lg:col-span-8 rounded-2xl border border-zinc-800 bg-zinc-950/30 p-6 space-y-4">
        <!-- Upload + botão -->
        <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div class="w-full">
            <label for="image-upload" class="block text-sm font-semibold mb-1">
              <span class="text-red-700">Imagem</span> (.jpg, .jpeg, .png, .webp, .avif)
            </label>
            <input
              id="image-upload"
              class="block w-full text-sm text-zinc-200 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0
                     file:bg-zinc-200 file:text-zinc-900 hover:file:opacity-90 disabled:opacity-60"
              type="file"
              accept="image/*"
              on:change={onFileChange}
              disabled={loading}
            />
          </div>

          <button
            class="px-6 py-3 rounded-xl font-semibold border border-zinc-700 hover:border-zinc-500 hover:opacity-90 disabled:opacity-50"
            on:click={calculate}
            disabled={loading || !file}
            type="button"
          >
            Calcular
          </button>
        </div>

        <!-- Loading card -->
        {#if loading}
          <div class="rounded-xl border border-zinc-800 bg-zinc-900/20 p-4">
            <p class="text-sm text-zinc-300">
              <span class="text-red-700 font-semibold">A processar</span> a imagem… (deteção + cálculo)
            </p>
            <div class="mt-3 h-2 w-full rounded-full bg-zinc-800 overflow-hidden">
              <div class="h-2 w-1/3 bg-red-700/80 rounded-full animate-pulse"></div>
            </div>
            <p class="text-xs text-zinc-400 mt-2">
              Isto pode demorar alguns segundos.
            </p>
          </div>
        {/if}

        {#if error}
          <div class="rounded-xl border border-red-900/40 bg-red-900/10 p-4">
          <div class="font-semibold text-red-400">Nenhum prato detetado</div>
          <p class="text-sm text-red-200 mt-1">{error}</p>
        </div>
        {/if}

        {#if data}
          <!-- Cards -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="rounded-xl border border-zinc-800 p-4 bg-zinc-900/20">
              <div class="text-sm text-zinc-400">Desperdício</div>
              <div class="text-3xl font-bold">
                {(data.waste_percentage ?? 0).toFixed(1)}%
              </div>
              <div class="text-xs text-zinc-400 mt-1">
                Estimado pela área dos alimentos no prato (pixéis).
              </div>
            </div>

            <div class="rounded-xl border border-zinc-800 p-4 bg-zinc-900/20">
              <div class="text-sm text-zinc-400">Calorias totais</div>
              <div class="text-3xl font-bold">
                {(data.calories?.total ?? 0).toFixed(2)} kcal
              </div>
              <div class="text-xs text-zinc-400 mt-1">
                Baseado em kcal/100g e porção estimada.
              </div>
            </div>
          </div>

          <!-- Botões -->
          <div class="flex flex-wrap gap-2">
            <button
              class="px-4 py-2 rounded-xl font-semibold border border-zinc-700 hover:border-zinc-500 hover:opacity-90"
              on:click={() => (showImages = !showImages)}
              type="button"
            >
              {showImages ? "Ocultar imagens" : "Ver imagens de deteção"}
            </button>
          </div>

          <!-- Detalhe por alimento -->
          <div class="rounded-xl border border-zinc-800 p-4 bg-zinc-900/20">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3">
              <h2 class="font-semibold">
                <span class="text-red-700">Detalhe</span> por alimentos
              </h2>

              <button
                class="px-4 py-2 rounded-xl font-semibold border border-zinc-700 hover:border-zinc-500 hover:opacity-90"
                on:click={() => (showTech = !showTech)}
                type="button"
              >
                {showTech ? "Ocultar detalhes" : "Ver detalhes"}
              </button>
            </div>

            {#if (data.calories?.items?.length ?? 0) === 0}
              <p class="text-sm text-zinc-400">
                Nenhum alimento estimado.
              </p>
            {:else}
              <ul class="space-y-2">
                {#each data.calories.items as it}
                  <li class="border border-zinc-800 rounded-xl p-3 bg-zinc-950/20">
                    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                      <div class="font-semibold">
                        {it.label_name}
                        {#if it.count && it.count > 1}
                          <span class="text-xs text-zinc-400"> (x{it.count})</span>
                        {/if}
                      </div>

                      <!-- ESSENCIAL -->
                      <div class="text-sm text-zinc-300 flex flex-wrap gap-x-3 gap-y-1">
                        <span>g: <b class="text-zinc-200">{it.grams_est}</b></span>
                        <span>kcal: <b class="text-zinc-200">{it.kcal_estimated}</b></span>
                      </div>
                    </div>

                    <!-- TÉCNICO -->
                    {#if showTech}
                      <div class="text-xs text-zinc-400 mt-2">
                        conf: {(it.confidence * 100).toFixed(1)}%
                        · porção: {(it.portion_ratio * 100).toFixed(1)}%
                        · kcal/100g: {it.kcal_per_100g}
                        {#if it.area}
                          · area: {it.area}
                        {/if}
                      </div>
                    {/if}
                  </li>
                {/each}
              </ul>
            {/if}
          </div>

          <!-- Imagens (thumbnails + modal) -->
          {#if showImages}
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              {#if data.image_base64}
                <button
                  class="text-left rounded-xl border border-zinc-800 p-4 bg-zinc-900/20 space-y-2 hover:border-zinc-500"
                  on:click={() => openModal("Imagem com deteções", data.image_base64)}
                  type="button"
                >
                  <h2 class="font-semibold">
                    <span class="text-red-700">Imagem</span> com deteções
                  </h2>
                  <img class="rounded-xl w-full" src={`data:image/jpeg;base64,${data.image_base64}`} alt="detections" />
                  <p class="text-xs text-zinc-400">Clica para ampliar</p>
                </button>
              {/if}

              {#if data.clustering_image_base64}
                <button
                  class="text-left rounded-xl border border-zinc-800 p-4 bg-zinc-900/20 space-y-2 hover:border-zinc-500"
                  on:click={() => openModal("Clustering", data.clustering_image_base64)}
                  type="button"
                >
                  <h2 class="font-semibold">
                    <span class="text-red-700">Clustering</span>
                  </h2>
                  <img class="rounded-xl w-full" src={`data:image/jpeg;base64,${data.clustering_image_base64}`} alt="clustering" />
                  <p class="text-xs text-zinc-400">Clica para ampliar</p>
                </button>
              {/if}
            </div>
          {/if}
        {/if}
      </section>
    </div>
  </div>

  {#if modalOpen}
    <div class="fixed inset-0 z-50 bg-black/80 p-4">
      <!-- Overlay clicável -->
      <button
        type="button"
        class="absolute inset-0 w-full h-full cursor-default"
        aria-label="Fechar modal"
        on:click={closeModal}
      ></button>

      <div class="relative w-full h-full flex items-center justify-center">
        <div
          class="w-full max-w-6xl rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-label={modalTitle}
        >
          <div class="flex items-center justify-between gap-3 mb-3">
            <h3 class="font-semibold text-lg">
              <span class="text-red-700">{modalTitle}</span>
            </h3>

            <button
              class="px-3 py-2 rounded-xl font-semibold border border-zinc-700 hover:border-zinc-500 hover:opacity-90"
              on:click={closeModal}
              type="button"
            >
              ✕ Fechar
            </button>
          </div>

          <div class="rounded-xl border border-zinc-800 bg-black/20 p-2 max-h-[80vh] overflow-auto">
            <img class="w-full h-auto rounded-xl" src={modalSrc} alt={modalTitle} />
          </div>

          <p class="text-xs text-zinc-400 mt-2">
            <b>ESC</b> para fechar.
          </p>
        </div>
      </div>
    </div>
  {/if}
</main>
