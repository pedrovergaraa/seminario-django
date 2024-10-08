# -*- coding: UTF-8 -*-


from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import models



# app.models.py
class Autor(models.Model):
    # Los autores se identifican por un id secuencial y se registra de ellos una descripción
    # compuesta por su pseudónimo o nombre y apellido.

    # id = models.BigIntegerField(primary_key=True)  <--Django lo hace en forma predeterminada
    nombre = models.CharField(max_length=30, null=True, blank=True)
    apellido = models.CharField(max_length=30, null=True, blank=True)
    pseudonimo = models.CharField(max_length=30, verbose_name='Pseudónimo', null=True, blank=True)
    modificado = models.DateTimeField(auto_now=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Autores'
        # db_table = 'autores' por defecto app_name_classname en este caso app_autor

    def __str__(self):
        return self.pseudonimo if self.pseudonimo else "{} {}".format(self.nombre, self.apellido)


class Genero(models.Model):
    descripcion = models.CharField(max_length=30, unique=True, verbose_name="Descripción")

    class Meta:
        verbose_name = 'Género'  # ← Podemos definir el nombre para mostrar de la clase
        verbose_name_plural = 'Géneros'  # ← Django pluraliza agregando 's' al final del nombre de la clase

    def __str__(self):
        return self.descripcion


class Libro(models.Model):
    """
    Los libros se identifican mediante su ISBN, tienen un título, cantidad de páginas, uno o más autores y
    pertenecen a un género literario.
    """
    from sorl.thumbnail import ImageField as SorlImageField

    def validate_isbn13(value):
        """Valida que el ISBN tenga exactamente 13 dígitos """
        if len(value) != 13 or not value.isdigit():
            raise ValidationError(f'El ISBN debe contener exactamente 13 dígitos. "{value}" no es válido.')

    isbn = models.CharField(max_length=13, primary_key=True, validators=[validate_isbn13])
    titulo = models.CharField(max_length=70, verbose_name="Título")
    cant_pag = models.IntegerField(default=0, verbose_name="Cant. de páginas")
    cant_ej = models.IntegerField(default=0, verbose_name="Cant. de ejemplares", editable=True)
    remanente = models.IntegerField(default=0, verbose_name="Ejemplares a disposición", editable=True)
    genero = models.ForeignKey(Genero, on_delete=models.PROTECT, verbose_name="Género")
    autores = models.ManyToManyField(Autor, verbose_name="Autores", through='LibroAutor')
    portada = SorlImageField(max_length=255, null=True, blank=True, upload_to='libros/%Y')

    def __str__(self):
        return self.titulo

    def isbn(self):
        try:
            isbn = str(self.id)
            return "-".join([isbn[0:3], isbn[3:4], isbn[4:6], isbn[6:12], isbn[12]])
        except:
            return "completar ISBN"

    def thumb_libro(self):
        from django.utils.safestring import mark_safe
        from sorl.thumbnail import get_thumbnail
        try:
            from django.urls import reverse
            return mark_safe(
                f'<a href=\"{reverse("admin:app_libro_change", args=[self.pk])}\" target="_blank">'
                f'<img src="{get_thumbnail(self.portada, "100", crop="center", quality=95).url}" /></a>')
        except:
            pass
        return ""
    thumb_libro.short_description = "Portada"



class LibroAutor(models.Model):
    libro = models.ForeignKey(Libro, on_delete=models.CASCADE)
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'Libros autores'

    def __str__(self):
        return "{} {}".format(self.autor, self.libro)


class Ejemplar(models.Model):
    libro = models.ForeignKey(Libro, on_delete=models.CASCADE)
    nro_ejemplar = models.IntegerField()

    class Meta:
        unique_together = ('libro', 'nro_ejemplar')
        verbose_name_plural = "Ejemplares"

    def __str__(self):
        return "{}-{}".format(self.nro_ejemplar, self.libro)

    def save(self, *args, **kwargs):
        from django.db.models import Max
        if not self.pk:
            self.nro_ejemplar = self.libro.ejemplar_set.aggregate(
                Max("nro_ejemplar", default=0))['nro_ejemplar__max'] + 1
        super().save(*args, **kwargs)


from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=Ejemplar)
@receiver(post_save, sender=Ejemplar)
def cant_ejemp_disp(sender, instance, **kwargs):
    """
    Actualizo la cantidad de ejemplares disponibles
    :param sender:
    :param instance:
    :param kwargs:
    :return:
    """
    creado = kwargs.get('created', False)
    signal = kwargs.get('signal', False)
    if creado:
        libro = instance.libro
        libro.cant_ej += 1
        libro.remanente += 1
        super(Libro, libro).save(update_fields=['cant_ej', 'remanente'])
    elif signal == post_delete:
        libro = instance.libro
        libro.cant_ej -= 1
        libro.remanente -= 1
        super(Libro, libro).save(update_fields=['cant_ej', 'remanente'])
    pass


class Socio(models.Model):
    dni = models.CharField(max_length=10, verbose_name="DNI", unique=True)
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    email = models.EmailField(max_length=50)
    direccion = models.CharField(max_length=50)
    celular = models.CharField(max_length=20, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    fecha_nacimiento = models.DateField()

    def __str__(self):
        return "{}, {}".format(self.apellido, self.nombre)


class Bibliotecario(Socio):
    desde = models.DateTimeField(auto_now_add=True)
    usuario = models.OneToOneField(User, on_delete=models.PROTECT)


class Prestamo(models.Model):
    ejemplar = models.ForeignKey(Ejemplar, on_delete=models.PROTECT)
    socio = models.ForeignKey(Socio, on_delete=models.PROTECT)
    entrego = models.ForeignKey(Bibliotecario, on_delete=models.PROTECT, related_name='entrego')
    recibio = models.ForeignKey(Bibliotecario, on_delete=models.PROTECT, related_name='recibio', null=True, blank=True)
    fecha_max_dev = models.DateField(
        verbose_name="Fecha máxima de devolución", help_text="El socio debe devolver el libro antes de esta fecha.",
        editable=False
    )
    fecha_dev = models.DateField(verbose_name="Fecha de devolución", null=True, blank=True, editable=False)

    class Meta:
        verbose_name, verbose_name_plural = "Préstamo", "Préstamos"

    def __str__(self):
        return "{}".format(self.id)

    def save(self, *args, **kwargs):
        from datetime import date, timedelta
        hoy = date.today()
        if not self.fecha_max_dev:
            configuracion = Configuracion().load()
            fecha_maxima_devolucion = hoy + timedelta(days=configuracion.plazo_max_devolucion)
            self.fecha_max_dev = fecha_maxima_devolucion
        if self.recibio and not self.fecha_dev:
            self.fecha_dev = hoy
        super(Prestamo, self).save(*args, **kwargs)


@receiver(post_save, sender=Prestamo)
def act_prestamo(sender, instance, **kwargs):
    """
    Actualizo la cantidad de ejemplares disponibles
    :param sender:
    :param instance:
    :param kwargs:
    :return:
    """
    creado = kwargs.get('created', False)
    signal = kwargs.get('signal', False)
    if creado:
        libro = instance.ejemplar.libro
        libro.remanente -= 1
        super(Libro, libro).save(update_fields=['remanente'])
    elif instance.fecha_dev:
        libro = instance.ejemplar.libro
        libro.remanente += 1
        super(Libro, libro).save(update_fields=['remanente'])
    # pass


class PrestamoPendiente(Prestamo):
    class Meta:
        proxy = True


# Implementamos patrón Singleton para la configuración del sistema
# Singleton es un patrón de diseño creacional que nos permite asegurarnos de que una clase tenga una única instancia,
# a la vez que proporciona un punto de acceso global a dicha instancia
from singleton.models import SingletonModel
class Configuracion(SingletonModel):
    plazo_max_devolucion = models.IntegerField(
        default=3, verbose_name="Plazo máximo de devolución",
        help_text="Expresado en días"
    )
    cant_max_prest_act = models.IntegerField(default=3, verbose_name="Cant. máxima de préstamos activos")

    class Meta:
        verbose_name, verbose_name_plural = "Configuración", "Configuraciones"

    def __str__(self):
        return "Configuración sistema Biblioteca"
