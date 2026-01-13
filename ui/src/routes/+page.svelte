<script lang="ts">
  import { goto } from "$app/navigation";
</script>

<main class="min-h-screen flex items-center justify-center px-6">
  <div class="w-full max-w-3xl text-center space-y-10">
    <!-- Logo -->
    <div class="flex justify-center">
      <img
        src="/favicon.png"
        alt="Logo da aplicação"
        class="h-24 w-24"
      />
    </div>

    <!-- Nome da app -->
    <div class="space-y-2">
      <h1 class="text-4xl font-bold">FreeFood Insight</h1>
      <p class="text-muted-foreground text-lg">
        Plataforma para deteção de desperdício alimentar e contagem de calorias.
      </p>
    </div>

    <!-- Botões -->
    <div class="flex flex-col sm:flex-row gap-4 justify-center">
      <button
        class="px-6 py-3 rounded-xl font-semibold border hover:opacity-90"
        on:click={() => goto("/waste")}
      >
        Desperdício Alimentar (App Base)
      </button>

      <button
        class="px-6 py-3 rounded-xl font-semibold border hover:opacity-90"
        on:click={() => goto("/calories")}
      >
        Contador de Calorias (Nova App)
      </button>
    </div>
  </div>
</main>
