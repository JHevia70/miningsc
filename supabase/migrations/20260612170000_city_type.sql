-- Las ciudades en superficie de planeta/luna/asteroide tienen type='city'.
-- No se renderizan como objetos en el mapa; su posición de escena es la del padre.

update public.bodies set type = 'city'
where key in ('lorville', 'area18', 'new_babbage', 'orison', 'levski');
