<script lang="ts">
  import { goto } from "$app/navigation";
</script>

<main class="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center px-6 py-14">
  <div class="w-full max-w-4xl">
    <!-- Card central -->
    <div class="rounded-3xl border border-zinc-800 bg-zinc-900/40 backdrop-blur px-8 py-10 shadow-2xl">
      <!-- Header -->
      <div class="text-center space-y-4">
        <div class="flex justify-center">
          <div class="h-24 w-24 rounded-2xl bg-zinc-950 border border-zinc-800 flex items-center justify-center">
            <img src="/favicon.png" alt="Logo" class="h-16 w-16 opacity-90" />
          </div>
        </div>

        <h1 class="text-4xl sm:text-5xl font-extrabold tracking-tight text-red-800">
          FreeFood Insight
        </h1>

        <p class="text-zinc-300 max-w-2xl mx-auto">
          Plataforma para deteção de desperdício alimentar e contagem de calorias.
        </p>
      </div>

      <!-- Separador -->
      <div class="my-10 h-px w-full bg-zinc-800/80"></div>

      <!-- Botões -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <button
          class="group w-full rounded-2xl border border-zinc-800 bg-zinc-950 px-6 py-5 text-left hover:border-red-800/60 hover:bg-zinc-950/70 transition"
          on:click={() => goto("/waste")}
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="text-lg font-semibold">Desperdício Alimentar</div>
              <div class="text-zinc-400 text-sm mt-1">
                Aceder à aplicação base de deteção e cálculo de desperdício (%).
              </div>
            </div>
            <span class="text-zinc-400 group-hover:text-red-700 transition">→</span>
          </div>
        </button>

        <button
          class="group w-full rounded-2xl border border-zinc-800 bg-zinc-950 px-6 py-5 text-left hover:border-red-800/60 hover:bg-zinc-950/70 transition"
          on:click={() => goto("/calories")}
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="text-lg font-semibold">Contador de Calorias</div>
              <div class="text-zinc-400 text-sm mt-1">
                Identificação de alimentos e estimativa de calorias com base na porção detatada detetada no prato.
              </div>
            </div>
            <span class="text-zinc-400 group-hover:text-red-700 transition">→</span>
          </div>
        </button>
      </div>

      <!-- Rodapé -->
      <div class="mt-10 text-center text-xs text-zinc-500">
        © {new Date().getFullYear()} FreeFood Insight • Versão académica
      </div>
    </div>
  </div>
</main>
