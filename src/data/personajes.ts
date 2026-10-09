// Personajes de GTA VI. "bio" resume con palabras propias lo que cuenta Rockstar en su web oficial
// (rockstargames.com/VI/only-in-leonida). Los rumores van aparte, siempre atribuidos a un medio.

export interface Rumor { texto: string; medio: string; url: string; fecha: string }
export interface Personaje {
  slug: string;
  nombre: string;
  rol: string;            // una línea para tarjetas
  titulo: string;         // <title> SEO
  descripcion: string;    // meta description
  frase: string;          // lema oficial (cita corta)
  bio: string[];
  imagenes: string[];     // slugs de /img/oficial/
  relaciones: string[];   // slugs de otros personajes
  rumores: Rumor[];
}

export const PERSONAJES: Personaje[] = [
  {
    slug: 'jason-duval',
    nombre: 'Jason Duval',
    rol: 'Protagonista. Exmilitar que trabaja para narcos en los cayos.',
    titulo: 'Jason Duval en GTA 6: quién es, historia y rumores',
    descripcion: 'Quién es Jason Duval, el protagonista de GTA 6: su pasado en el ejército, su trabajo en los cayos de Leonida, su relación con Lucía y las teorías de los fans.',
    frase: 'Pase lo que pase, puedes contar conmigo.',
    bio: [
      'Jason creció rodeado de estafadores y delincuentes. Para dejar atrás una adolescencia complicada se alistó en el ejército, pero al salir terminó en los cayos de Leonida haciendo lo que mejor se le da: encargos para narcotraficantes de la zona.',
      'Según Rockstar, lo que Jason quiere es una vida tranquila, aunque todo se le complica. Vive en una propiedad de Brian Heder a cambio de ayudarle con sus negocios, y su amigo Cal Hampton es otro de los socios de Brian.',
      'Conocer a Lucía puede ser lo mejor o lo peor que le haya pasado. Él tiene claro cómo le gustaría que acabara su historia juntos, pero de momento nadie lo sabe.',
    ],
    imagenes: ['jason-duval-1', 'jason-duval-2', 'jason-duval-3', 'jason-duval-4'],
    relaciones: ['lucia-caminos', 'cal-hampton', 'brian-heder'],
    rumores: [
      { texto: 'Una de las teorías más comentadas sostiene que Jason podría ser un policía infiltrado. Los fans se fijan en detalles de los tráileres, como un pantalón parecido al de los SWAT o un personaje que le pregunta si es un «Fed». El propio medio la pone en duda.', medio: 'GameStar', url: 'https://www.gamestar.de/artikel/gta-6-ist-jason-ein-undercover-cop,3459550.html', fecha: 'septiembre de 2026' },
      { texto: 'Parte de la comunidad cree que Jason podría morir al final de la historia, por la cicatriz de su cara (parecida a las de Arthur Morgan y John Marston en Red Dead) y por el paralelismo con Bonnie y Clyde.', medio: 'Dexerto', url: 'https://www.dexerto.com/gta/gta-6-fans-convinced-theyve-already-spoiled-the-ending-2596370/', fecha: 'marzo de 2024' },
      { texto: 'Los fans señalan al actor Dylan Rourke como intérprete de Jason por su parecido físico y de voz. Ni Rockstar ni el actor lo han confirmado.', medio: 'PCGamesN', url: 'https://www.pcgamesn.com/grand-theft-auto-6/voice-actors', fecha: '2023, actualizado después' },
    ],
  },
  {
    slug: 'lucia-caminos',
    nombre: 'Lucía Caminos',
    rol: 'Protagonista. Recién salida de la prisión de Leonida.',
    titulo: 'Lucía Caminos en GTA 6: quién es, historia y rumores',
    descripcion: 'Quién es Lucía Caminos, la protagonista de GTA 6: su paso por la cárcel de Leonida, su familia, su plan con Jason y las teorías de los fans.',
    frase: 'Lo único que importa es a quién conoces y lo que tienes.',
    bio: [
      'Su padre le enseñó a pelear casi antes de que aprendiera a andar, y la vida no ha dejado de ponerla a prueba desde entonces. Defender a su familia la llevó a la penitenciaría de Leonida, de la que salió, según Rockstar, gracias a la suerte.',
      'Lucía sale de prisión con una idea fija: a partir de ahora, solo decisiones inteligentes. Tiene un plan y está dispuesta a cumplirlo cueste lo que cueste.',
      'Una vida junto a Jason puede ser su oportunidad para salir adelante. Es la primera protagonista femenina jugable de la saga en la era moderna.',
    ],
    imagenes: ['lucia-caminos-1', 'lucia-caminos-2', 'lucia-caminos-3', 'lucia-caminos-4'],
    relaciones: ['jason-duval'],
    rumores: [
      { texto: 'Los fans creen que la actriz neoyorquina Manni L. Perez da vida a Lucía por su parecido físico y de voz. No hay confirmación oficial y la actriz no lo ha confirmado.', medio: 'Insider Gaming', url: 'https://insider-gaming.com/gta-6-lucia-voice-actor/', fecha: 'diciembre de 2023' },
      { texto: 'Ha vuelto a cobrar fuerza la teoría de que Lucía acabará traicionando a Jason, después de que los fans vieran una rata escondida en una captura oficial (en inglés, «rat» también significa chivato).', medio: 'TheGamer', url: 'https://opencritic.com/news/33899/gta-6-fans-have-always-thought-lucia-was-suspicious-and-now-a-rat-is-being-taken-as-foreshadowing', fecha: 'junio de 2026' },
      { texto: 'Tras el primer tráiler se hizo viral la teoría de que la mujer del bikini blanco que aparece en un yate es Lucía, quizá infiltrada entre la clase alta durante alguna misión.', medio: '3DJuegos', url: 'https://www.3djuegos.com/juegos/grand-theft-auto-vi/noticias/debate-siglo-nueva-teoria-trailer-gta-6-asegura-que-mujer-bikini-realmente-lucia', fecha: 'diciembre de 2023' },
    ],
  },
  {
    slug: 'cal-hampton',
    nombre: 'Cal Hampton',
    rol: 'Amigo de Jason, paranoico y socio de Brian.',
    titulo: 'Cal Hampton en GTA 6: quién es el amigo de Jason',
    descripcion: 'Quién es Cal Hampton en GTA 6: el amigo paranoico de Jason, socio de Brian Heder, y quién podría ponerle voz según los fans.',
    frase: '¿Y si todo lo que dicen en Internet fuera verdad?',
    bio: [
      'Cal es amigo de Jason y otro de los socios de Brian Heder. Donde mejor está es en casa, escuchando las comunicaciones de la guardia costera con unas cervezas y el navegador lleno de pestañas privadas.',
      'Rockstar lo presenta como alguien del escalón más bajo de la sociedad estadounidense al que eso no le preocupa. Su paranoia es contagiosa, pero Jason aspira a algo más.',
    ],
    imagenes: ['cal-hampton-1', 'cal-hampton-2', 'cal-hampton-3'],
    relaciones: ['jason-duval', 'brian-heder'],
    rumores: [
      { texto: 'Después de oír más a Cal en «Una mirada extendida», muchos fans creen que su voz es la del cómico de Saturday Night Live Bobby Moynihan. Antes, muchos apostaban por el cocinero Matty Matheson. Rockstar no lo ha confirmado.', medio: 'SVG', url: 'https://www.svg.com/2246330/gta-6-extended-look-actors-voice-cast/', fecha: 'agosto de 2026' },
    ],
  },
  {
    slug: 'boobie-ike',
    nombre: 'Boobie Ike',
    rol: 'Leyenda de Vice City con un imperio de negocios.',
    titulo: 'Boobie Ike en GTA 6: quién es la leyenda de Vice City',
    descripcion: 'Quién es Boobie Ike en GTA 6: la leyenda local de Vice City con inmobiliarias, un club de striptease y un estudio de grabación.',
    frase: 'El Jack of Hearts te robará el corazón.',
    bio: [
      'Boobie es una leyenda local en Vice City y se comporta como tal. Es de los pocos que supo aprovechar sus años en la calle para levantar un imperio legal: propiedades inmobiliarias, un club de striptease y un estudio de grabación.',
      'Siempre está sonriendo, hasta que toca hablar de negocios. Lo que de verdad le importa es su sociedad con Dre\'Quan Priest al frente del sello Only Raw Records. Solo les falta un éxito.',
    ],
    imagenes: ['boobie-ike-1', 'boobie-ike-2', 'boobie-ike-3'],
    relaciones: ['dre-quan-priest', 'real-dimez'],
    rumores: [],
  },
  {
    slug: 'dre-quan-priest',
    nombre: "Dre'Quan Priest",
    rol: 'Aspirante a magnate musical al frente de Only Raw Records.',
    titulo: "Dre'Quan Priest en GTA 6: quién es el jefe de Only Raw Records",
    descripcion: "Quién es Dre'Quan Priest en GTA 6: el buscavidas que dirige el sello Only Raw Records con Boobie Ike y que ha fichado a Real Dimez.",
    frase: 'Only Raw... Records.',
    bio: [
      "Dre'Quan siempre fue más buscavidas que gánster. Incluso cuando vendía droga en la calle para llegar a fin de mes, su objetivo era entrar en la industria musical.",
      'Ahora dirige Only Raw Records junto a Boobie Ike y acaba de fichar a Real Dimez. Sus días buscando artistas para el club de Boobie podrían estar contados: quiere conquistar la escena musical de Vice City.',
    ],
    imagenes: ['dre-quan-priest-1', 'dre-quan-priest-2', 'dre-quan-priest-3'],
    relaciones: ['boobie-ike', 'real-dimez'],
    rumores: [
      { texto: "Algunos fans relacionan a Dre'Quan con el actor Reggie Talley, que llegó a incluir en su currículum un proyecto de Rockstar y después lo borró. Es una especulación sin confirmar.", medio: 'SVG', url: 'https://svg.com/2120810/gta-6-rumored-cast-look-real-life', fecha: 'marzo de 2026' },
    ],
  },
  {
    slug: 'real-dimez',
    nombre: 'Real Dimez',
    rol: 'Dúo de rap formado por Bae-Luxe y Roxy.',
    titulo: 'Real Dimez en GTA 6: quiénes son Bae-Luxe y Roxy',
    descripcion: 'Quiénes son Real Dimez en GTA 6: el dúo de rap de Bae-Luxe y Roxy, amigas desde el instituto, que acaban de fichar por Only Raw Records.',
    frase: 'Vídeos virales y temas pegadizos.',
    bio: [
      'Bae-Luxe y Roxy son amigas desde el instituto y forman Real Dimez. Han sabido convertir sus andanzas por el barrio en dinero gracias a temas de rap atrevidos y a su presencia constante en redes sociales.',
      'Su primer éxito, junto al rapero local DWNPLY, las llevó a lo más alto. Cinco años y unos cuantos problemas después, han firmado con Only Raw Records y buscan volver a dar el golpe.',
    ],
    imagenes: ['real-dimez-1', 'real-dimez-2', 'real-dimez-3'],
    relaciones: ['dre-quan-priest', 'boobie-ike'],
    rumores: [],
  },
  {
    slug: 'raul-bautista',
    nombre: 'Raúl Bautista',
    rol: 'Atracador de bancos veterano y cada vez más temerario.',
    titulo: 'Raúl Bautista en GTA 6: quién es el atracador de bancos',
    descripcion: 'Quién es Raúl Bautista en GTA 6: el atracador de bancos con experiencia que busca gente con agallas, y qué dicen los rumores sobre él.',
    frase: 'La experiencia es un grado.',
    bio: [
      'Seguro de sí mismo, carismático y astuto: Raúl es un atracador de bancos con experiencia que siempre anda buscando gente con agallas, dispuesta a arriesgarse por los botines más grandes.',
      'Con cada golpe se vuelve más temerario. Tarde o temprano, su equipo tendrá que elegir entre subir la apuesta o retirarse.',
    ],
    imagenes: ['raul-bautista-1', 'raul-bautista-2', 'raul-bautista-3'],
    relaciones: ['jason-duval', 'lucia-caminos'],
    rumores: [
      { texto: 'Los fans creen que el actor español Óscar Jaenada interpreta a Raúl, por su parecido y por una foto en su Instagram con una camiseta del personaje. Ni Rockstar ni el actor lo han confirmado.', medio: 'GamePro', url: 'https://www.gamepro.de/artikel/gta-6-raul-bautista-schauspieler,3433582.html', fecha: 'mayo de 2025' },
      { texto: 'Una teoría surgida en Reddit apunta a que Raúl podría ser el traidor de la historia, por su parecido con un policía que aparece en el segundo tráiler. El medio subraya que no hay pruebas.', medio: 'Notebookcheck', url: 'https://www.notebookcheck.net/GTA-6-New-theory-turns-previous-traitor-suspicions-on-their-head.1369398.0.html', fecha: 'agosto de 2026' },
    ],
  },
  {
    slug: 'brian-heder',
    nombre: 'Brian Heder',
    rol: 'Contrabandista veterano de los cayos y casero de Jason.',
    titulo: 'Brian Heder en GTA 6: quién es y quién le pone voz',
    descripcion: 'Quién es Brian Heder en GTA 6: el contrabandista de los cayos que da casa a Jason, su esposa Lori y el actor que le pone voz.',
    frase: 'No hay nada mejor que tomarse un mudslide al atardecer.',
    bio: [
      'Brian es un narcotraficante de la vieja escuela, de la época dorada del contrabando en los cayos. Sigue en el negocio desde su astillero, junto a su tercera esposa, Lori, aunque ya deja que otros hagan el trabajo sucio.',
      'Parece un hippie playero, pero según Rockstar ataca como un tiburón blanco. Deja que Jason viva gratis en una de sus propiedades a cambio de que le ayude a presionar a los vecinos y se pase de vez en cuando a tomar la sangría de Lori.',
    ],
    imagenes: ['brian-heder-1', 'brian-heder-2', 'brian-heder-3'],
    relaciones: ['jason-duval', 'cal-hampton'],
    rumores: [
      { texto: 'El actor Stephen Root (King of the Hill, Office Space) confirmó en una entrevista con Associated Press que participa en GTA 6, y los medios lo identifican como la voz de Brian. La confirmación viene del actor, no de Rockstar.', medio: 'Dexerto', url: 'https://www.dexerto.com/gta/gta-6-actor-confirms-hes-in-the-game-after-trying-to-keep-it-secret-3408818/', fecha: 'septiembre de 2026' },
    ],
  },
];

export const bySlug = (s: string) => PERSONAJES.find((p) => p.slug === s);
