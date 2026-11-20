package dev.qumara.combat.attack;

import java.util.function.Supplier;

/** Catalogo de ataques con su logica de seleccion por distancia (la IA elige segun estos pesos). */
public enum AttackType {
    SLAM(SlamAttack::new, 60) {
        public int weight(double d, int players, boolean fury) { return d < 3.2 || d > 9.5 ? 0 : (d < 7 ? 6 : 4); }
    },
    SWEEP(SweepAttack::new, 80) {
        public int weight(double d, int players, boolean fury) { return d < 2.2 || d > 7.2 ? 0 : (fury ? 6 : 5); }
    },
    TONGUE(TongueAttack::new, 100) {
        public int weight(double d, int players, boolean fury) { return d < 3.5 || d > 10.0 ? 0 : 5; }
    },
    ROOTS(RootsAttack::new, 160) {
        public int weight(double d, int players, boolean fury) { return 3 + Math.min(players - 1, 2) + (d > 12 ? 1 : 0); }
    },
    GARDEN(GardenAttack::new, 520) {
        public int weight(double d, int players, boolean fury) { return d > 9 ? 5 : 2 + Math.min(players - 1, 2); }
    },
    VINE(VineAttack::new, 120) {
        public int weight(double d, int players, boolean fury) { return d > 12 ? 6 : (d > 6 ? 4 : 2); }
    };

    private final Supplier<BossAttack> factory;
    public final int cooldownTicks;
    AttackType(Supplier<BossAttack> f, int cd) { this.factory = f; this.cooldownTicks = cd; }
    public BossAttack create() { return factory.get(); }
    /** 0 = no usable a esta distancia. */
    public abstract int weight(double dist, int players, boolean fury);
}
